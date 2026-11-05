"""Benchmark des services d'IA (compétence C7).

Principe : le MÊME jeu de publications annotées à la main est envoyé, avec le MÊME
prompt et les MÊMES paramètres, à chaque service. On mesure :
  - F1 exactitude du classement (vs annotation humaine) ;
  - F2 écart absolu moyen de la note de pertinence ;
  - F3 part des résumés rédigés en français (heuristique) – la fidélité se juge à la relecture ;
  - F4 part des réponses JSON conformes au schéma ;
  - latence (moyenne, 95e centile), tokens et coût estimé.
Les réponses brutes sont conservées pour la relecture humaine des résumés.
"""

from __future__ import annotations

import csv
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .analyse import analyser_article
from .config import Config, Fournisseur
from .ia_client import ClientIA, ErreurServiceIA
from .monitoring import percentile
from .stockage import Stockage

log = logging.getLogger("veilleia.benchmark")

MOTS_FR = {"le", "la", "les", "des", "une", "est", "et", "du", "pour", "dans", "qui", "sur", "avec", "par",
           "au", "aux", "ce", "cette", "sont", "son", "ses", "leur", "à", "été", "être", "d'un", "d'une"}
MOTS_EN = {"the", "and", "of", "to", "is", "in", "for", "with", "on", "that", "this", "are", "by", "its"}


def est_en_francais(texte: str) -> bool:
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", texte.lower())
    fr = sum(m in MOTS_FR for m in mots)
    en = sum(m in MOTS_EN for m in mots)
    return fr > en


# ---------------------------------------------------------------------------
# Jeu de test
# ---------------------------------------------------------------------------
def constituer_jeu_test(stockage: Stockage, chemin: Path, taille: int = 30, graine: int = 42) -> int:
    """Tire un échantillon équilibré par source, à annoter à la main (categorie, pertinence)."""
    lignes = [dict(r) for r in stockage.cnx.execute(
        "SELECT id, source_id, titre, url, date_pub, contenu FROM articles ORDER BY date_pub DESC")]
    par_source: dict[str, list[dict]] = {}
    for a in lignes:
        par_source.setdefault(a["source_id"], []).append(a)
    alea = random.Random(graine)  # noqa: S311 – tirage reproductible, pas d'usage cryptographique
    for liste in par_source.values():
        alea.shuffle(liste)
    echantillon: list[dict] = []
    while len(echantillon) < taille and any(par_source.values()):
        for src in sorted(par_source):
            if par_source[src] and len(echantillon) < taille:
                echantillon.append(par_source[src].pop())
    jeu = {
        "description": "Jeu de test du benchmark VeilleIA. Annoter à la main 'categorie' "
                       "(technique | reglementaire | offre_outil | hors_sujet) et 'pertinence' (1 à 5) "
                       "pour la DSI d'un Département, AVANT de lancer le benchmark.",
        "constitue_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "articles": [{**a, "annotation": {"categorie": None, "pertinence": None, "commentaire": ""}}
                     for a in echantillon],
    }
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(jeu, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(echantillon)


def charger_jeu_test(chemin: Path) -> list[dict]:
    jeu = json.loads(chemin.read_text(encoding="utf-8"))
    articles = jeu["articles"]
    non_annotes = [a["id"] for a in articles
                   if a["annotation"].get("categorie") is None or a["annotation"].get("pertinence") is None]
    if non_annotes:
        raise ValueError(f"{len(non_annotes)} article(s) non annoté(s) dans {chemin.name} : "
                         "compléter 'categorie' et 'pertinence' avant le benchmark.")
    return articles


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------
@dataclass
class ResultatService:
    fournisseur: str
    libelle: str
    modele: str
    nb: int = 0
    json_ok: int = 0
    categorie_ok: int = 0
    ecarts_pertinence: list[int] = field(default_factory=list)
    resumes_fr: int = 0
    latences: list[float] = field(default_factory=list)
    tokens_entree: int = 0
    tokens_sortie: int = 0
    cout_eur: float | None = None
    erreurs: list[str] = field(default_factory=list)

    def resume(self) -> dict:
        n = self.nb or 1
        ok = self.json_ok or 1
        return {
            "fournisseur": self.fournisseur,
            "service": self.libelle,
            "modele": self.modele,
            "articles": self.nb,
            "F4_json_conforme_pct": round(100 * self.json_ok / n, 1),
            "F1_exactitude_pct": round(100 * self.categorie_ok / ok, 1) if self.json_ok else None,
            "F2_ecart_moyen": round(sum(self.ecarts_pertinence) / len(self.ecarts_pertinence), 2)
            if self.ecarts_pertinence else None,
            "F3_resume_fr_pct": round(100 * self.resumes_fr / ok, 1) if self.json_ok else None,
            "latence_moy_s": round(sum(self.latences) / len(self.latences), 2) if self.latences else None,
            "latence_p95_s": round(percentile(self.latences, 0.95), 2) if self.latences else None,
            "tokens_total": self.tokens_entree + self.tokens_sortie,
            "cout_estime_eur": round(self.cout_eur, 4) if self.cout_eur is not None else None,
            "erreurs": len(self.erreurs),
        }


def evaluer_service(fournisseur: Fournisseur, config: Config, articles: list[dict], stockage: Stockage,
                    dossier_brut: Path, client: ClientIA | None = None) -> ResultatService:
    prod = config.production
    modele = fournisseur.modele(prod["modele_analyse"])
    res = ResultatService(fournisseur.id, fournisseur.libelle, modele)
    client = client or ClientIA(fournisseur, stockage, timeout_s=prod["timeout_s"], tentatives=prod["tentatives"])
    dossier_brut.mkdir(parents=True, exist_ok=True)
    nb_appels_avant = stockage.compter("appels_ia")
    with (dossier_brut / f"{fournisseur.id}.jsonl").open("w", encoding="utf-8") as brut:
        for i, a in enumerate(articles, start=1):
            res.nb += 1
            ligne: dict = {"id": a["id"], "titre": a["titre"], "attendu": a["annotation"]}
            try:
                sortie = analyser_article(client, config, a["titre"], a["source_id"], a["contenu"],
                                          tache="benchmark")
                res.json_ok += 1
                res.categorie_ok += int(sortie.categorie == a["annotation"]["categorie"])
                res.ecarts_pertinence.append(abs(sortie.pertinence - int(a["annotation"]["pertinence"])))
                res.resumes_fr += int(est_en_francais(sortie.resume))
                ligne["obtenu"] = sortie.model_dump()
            except ErreurServiceIA as exc:
                res.erreurs.append(str(exc)[:200])
                ligne["erreur"] = str(exc)[:300]
                if exc.code_http in (401, 403):
                    log.error("%s : accès refusé, service ignoré.", fournisseur.libelle)
                    break
            brut.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            log.info("[%s %d/%d] %s", fournisseur.id, i, len(articles), "ok" if "obtenu" in ligne else "échec")
            time.sleep(prod.get("pause_entre_appels_s", 0))
    # Mesures techniques relevées par le connecteur pendant le passage
    appels = list(stockage.cnx.execute("SELECT * FROM appels_ia WHERE id > ? AND fournisseur = ?",
                                       (nb_appels_avant, fournisseur.id)))
    res.latences = [r["latence_s"] for r in appels if r["latence_s"] is not None and r["statut"] == "ok"]
    res.tokens_entree = sum(r["tokens_entree"] or 0 for r in appels)
    res.tokens_sortie = sum(r["tokens_sortie"] or 0 for r in appels)
    couts = [r["cout_eur"] for r in appels if r["cout_eur"] is not None]
    res.cout_eur = sum(couts) if couts else None
    return res


def ecrire_resultats(resultats: list[ResultatService], dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(UTC).strftime("%Y-%m-%d")
    lignes = [r.resume() for r in resultats]
    if lignes:
        with (dossier / f"resultats_{jour}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0]), delimiter=";")
            w.writeheader()
            w.writerows(lignes)
    (dossier / f"resultats_{jour}.json").write_text(
        json.dumps({"date": jour, "resultats": lignes, "erreurs": {r.fournisseur: r.erreurs for r in resultats}},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Résultats du benchmark – {jour}", "",
          "| Service | Modèle | JSON conforme (F4) | Exactitude classement (F1) | Écart pertinence (F2) "
          "| Résumés en français (F3) | Latence moy. / p95 | Tokens | Coût estimé | Erreurs |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in lignes:
        def v(x: object, suffixe: str = "") -> str:
            return "–" if x is None else f"{x}{suffixe}"
        md.append(f"| {r['service']} | {r['modele']} | {v(r['F4_json_conforme_pct'], ' %')} | "
                  f"{v(r['F1_exactitude_pct'], ' %')} | {v(r['F2_ecart_moyen'])} | {v(r['F3_resume_fr_pct'], ' %')} | "
                  f"{v(r['latence_moy_s'], ' s')} / {v(r['latence_p95_s'], ' s')} | {r['tokens_total']} | "
                  f"{v(r['cout_estime_eur'], ' €')} | {r['erreurs']} |")
    md += ["", "Lecture : F1 et F3 en pourcentage des réponses conformes ; F2 = écart absolu moyen entre la note "
           "du modèle et l'annotation humaine (0 = parfait). La fidélité des résumés se juge à la relecture des "
           "fichiers bruts (`resultats/brut/`)."]
    chemin = dossier / f"resultats_{jour}.md"
    chemin.write_text("\n".join(md) + "\n", encoding="utf-8")
    return chemin


def lancer_benchmark(config: Config, chemin_jeu: Path, dossier_resultats: Path,
                     fournisseurs: list[str] | None = None) -> tuple[list[ResultatService], Path]:
    articles = charger_jeu_test(chemin_jeu)
    candidats = [config.fournisseur(f) for f in fournisseurs] if fournisseurs else config.fournisseurs()
    stockage = Stockage(dossier_resultats / "brut" / "benchmark.db")
    resultats = []
    try:
        for f in candidats:
            if not f.est_configure():
                log.warning("%s ignoré : clé %s absente de .env", f.libelle, f.cle_env)
                continue
            log.info("=== %s (%s) – %d articles ===", f.libelle, f.modele(config.production["modele_analyse"]),
                     len(articles))
            try:
                resultats.append(evaluer_service(f, config, articles, stockage, dossier_resultats / "brut"))
            except ErreurServiceIA as exc:
                log.error("%s ignoré : %s", f.libelle, exc)
    finally:
        stockage.fermer()
    chemin = ecrire_resultats(resultats, dossier_resultats)
    return resultats, chemin

