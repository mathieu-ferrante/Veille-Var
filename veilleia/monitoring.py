"""Monitorage du service d'IA : indicateurs, alertes et tableau de bord HTML accessible.

Complète la console d'usage du fournisseur (consommation, facturation) par un suivi
propre au projet, calculé à partir de la table `appels_ia` :
  - taux d'erreur, latence moyenne et 95e centile, taux de JSON invalide ;
  - tokens et coût sur la fenêtre de surveillance ;
  - disponibilité des sources RSS lors de la dernière collecte.
Chaque indicateur est comparé à un seuil (config.yaml > monitorage.seuils).
"""

from __future__ import annotations

import html
import json
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .collecte import charger_sources
from .config import Config
from .stockage import Stockage

log = logging.getLogger("veilleia.monitoring")


@dataclass
class Indicateur:
    nom: str
    valeur: float | None
    seuil: float | None
    unite: str = ""
    description: str = ""

    @property
    def en_alerte(self) -> bool:
        return self.valeur is not None and self.seuil is not None and self.valeur > self.seuil

    def valeur_txt(self) -> str:
        if self.valeur is None:
            return "non disponible"
        if self.unite == "%":
            return f"{self.valeur * 100:.1f} %"
        if isinstance(self.valeur, float) and not self.valeur.is_integer():
            return f"{self.valeur:.3f} {self.unite}".strip()
        return f"{_milliers(self.valeur)} {self.unite}".strip()

    def seuil_txt(self) -> str:
        if self.seuil is None:
            return "–"
        return f"{self.seuil * 100:.0f} %" if self.unite == "%" else f"{_milliers(self.seuil)} {self.unite}".strip()


def _milliers(x: float) -> str:
    """Nombre lisible à la française : 2 000 000 plutôt que 2e+06 (espace insécable fine)."""
    if float(x).is_integer():
        return f"{int(x):,}".replace(",", " ")
    return f"{x:g}"


def percentile(valeurs: list[float], p: float) -> float | None:
    if not valeurs:
        return None
    v = sorted(valeurs)
    k = (len(v) - 1) * p
    bas, haut = math.floor(k), math.ceil(k)
    return v[int(k)] if bas == haut else v[bas] + (v[haut] - v[bas]) * (k - bas)


def _sources_actives(config: Config) -> list[str] | None:
    """Identifiants des sources actives de sources.yaml (None si le fichier est illisible : pas de filtre)."""
    try:
        return [s.id for s in charger_sources(config.chemin(config.collecte["fichier_sources"]))]
    except (OSError, ValueError, TypeError, KeyError):
        return None


def calculer_indicateurs(config: Config, stockage: Stockage) -> tuple[list[Indicateur], dict]:
    conf = config.monitorage
    seuils = conf["seuils"]
    appels = [dict(a) for a in stockage.appels_depuis(conf["fenetre_jours"])]
    appels_prod = [a for a in appels if a["tache"] in ("analyse", "synthese")]
    n = len(appels_prod)
    erreurs = [a for a in appels_prod if a["statut"] != "ok"]
    latences = [a["latence_s"] for a in appels_prod if a["latence_s"] is not None and a["statut"] == "ok"]
    avec_json = [a for a in appels_prod if a["json_valide"] is not None]
    json_ko = [a for a in avec_json if a["json_valide"] == 0]
    tokens = sum((a["tokens_entree"] or 0) + (a["tokens_sortie"] or 0) for a in appels_prod)
    couts = [a["cout_eur"] for a in appels_prod if a["cout_eur"] is not None]
    # Une synthèse ratée est noyée dans le taux d'erreur global (1 appel sur ~150) : indicateur dédié.
    syntheses = [a for a in appels_prod if a["tache"] == "synthese"]
    derniere_synthese_ko = float(syntheses[-1]["statut"] != "ok") if syntheses else None
    collectes = [dict(c) for c in stockage.derniere_collecte_par_source(_sources_actives(config))]
    sources_ko = [c for c in collectes if c["statut"] != "ok"]

    indicateurs = [
        Indicateur("Appels au service d'IA", float(n), None, "", "Nombre d'appels d'analyse et de synthèse"),
        Indicateur("Taux d'erreur", len(erreurs) / n if n else None, seuils["taux_erreur_max"], "%",
                   "Appels en échec définitif (après nouvelles tentatives)"),
        Indicateur("Dernière synthèse en échec", derniere_synthese_ko, 0, "",
                   "1 si le dernier appel de synthèse a échoué : la synthèse de la semaine n'est pas produite"),
        Indicateur("Latence moyenne", sum(latences) / len(latences) if latences else None, None, "s"),
        Indicateur("Latence 95e centile", percentile(latences, 0.95), seuils["latence_p95_max_s"], "s",
                   "95 % des appels sont plus rapides que cette valeur"),
        Indicateur("Réponses JSON non conformes", len(json_ko) / len(avec_json) if avec_json else None,
                   seuils["json_invalide_max"], "%", "Réponses rejetées par la validation du schéma"),
        Indicateur("Tokens consommés", float(tokens), seuils["tokens_hebdo_max"], "tokens"),
        Indicateur("Coût estimé", sum(couts) if couts else None, seuils["cout_hebdo_max_eur"], "€",
                   "Calculé si les prix sont renseignés dans config.yaml"),
        Indicateur("Sources RSS en erreur", float(len(sources_ko)), seuils["sources_en_erreur_max"], "",
                   "Lors de la dernière collecte de chaque source"),
    ]
    details = {
        "fenetre_jours": conf["fenetre_jours"],
        "par_modele": _par_modele(appels_prod),
        "dernieres_erreurs": [
            {"horodatage": a["horodatage"], "modele": a["modele"], "erreur": a["erreur"]} for a in erreurs[-10:]
        ],
        "sources_en_erreur": [{"source": c["source_id"], "erreur": c["erreur"]} for c in sources_ko],
    }
    return indicateurs, details


def _par_modele(appels: list[dict]) -> list[dict]:
    groupes: dict[str, list[dict]] = {}
    for a in appels:
        groupes.setdefault(f"{a['fournisseur']}/{a['modele']}", []).append(a)
    res = []
    for cle, liste in sorted(groupes.items()):
        ok = [a for a in liste if a["statut"] == "ok"]
        lat = [a["latence_s"] for a in ok if a["latence_s"] is not None]
        res.append({
            "modele": cle, "appels": len(liste), "succes": len(ok),
            "latence_moy_s": round(sum(lat) / len(lat), 2) if lat else None,
            "tokens": sum((a["tokens_entree"] or 0) + (a["tokens_sortie"] or 0) for a in liste),
        })
    return res


def verifier_alertes(indicateurs: list[Indicateur]) -> list[str]:
    alertes = [f"{i.nom} = {i.valeur_txt()} (seuil {i.seuil_txt()})" for i in indicateurs if i.en_alerte]
    for a in alertes:
        log.warning("ALERTE monitorage : %s", a)
    if not alertes:
        log.info("Monitorage : aucun seuil dépassé.")
    return alertes


def rendre_tableau_de_bord(indicateurs: list[Indicateur], details: dict, alertes: list[str]) -> str:
    e = html.escape
    lignes = "".join(
        f"<tr><th scope=\"row\">{e(i.nom)}<br><span class=\"meta\">{e(i.description)}</span></th>"
        f"<td>{e(i.valeur_txt())}</td><td>{e(i.seuil_txt())}</td>"
        f"<td>{'<strong>ALERTE</strong> – seuil dépassé' if i.en_alerte else 'Conforme'}</td></tr>"
        for i in indicateurs
    )
    modeles = "".join(
        f"<tr><th scope=\"row\">{e(m['modele'])}</th><td>{m['appels']}</td><td>{m['succes']}</td>"
        f"<td>{m['latence_moy_s'] if m['latence_moy_s'] is not None else '–'}</td><td>{m['tokens']}</td></tr>"
        for m in details["par_modele"]
    ) or '<tr><td colspan="5">Aucun appel sur la période</td></tr>'
    bloc_alertes = (
        "<ul>" + "".join(f"<li>{e(a)}</li>" for a in alertes) + "</ul>" if alertes
        else "<p>Aucun seuil dépassé sur la période.</p>"
    )
    erreurs = "".join(f"<li>{e(x['horodatage'])} – {e(x['modele'])} – {e(x['erreur'] or '')}</li>"
                      for x in details["dernieres_erreurs"]) or "<li>Aucune</li>"
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitorage VeilleIA – {datetime.now(UTC):%d/%m/%Y}</title>
<style>
:root {{ --t:#1a1a1a; --f:#fff; --a:#00436e; --b:#c8d3dc; --z:#eef3f7; }}
@media (prefers-color-scheme: dark) {{ :root {{ --t:#f0f0f0; --f:#121417; --a:#8cc8ff; --b:#3a4550; --z:#1d242b; }} }}
body {{ font-family: Arial, sans-serif; line-height:1.5; color:var(--t); background:var(--f); max-width:60rem;
       margin:0 auto; padding:0 1rem; }}
h1, h2 {{ color:var(--a); }} table {{ border-collapse:collapse; width:100%; margin-bottom:1.5rem; }}
caption {{ text-align:left; font-weight:bold; padding:.4rem 0; }}
th, td {{ border:1px solid var(--b); padding:.4rem; text-align:left; vertical-align:top; }}
thead th {{ background:var(--z); }} .meta {{ font-weight:normal; font-size:.9rem; }}
.encadre {{ background:var(--z); border-left:6px solid var(--a); padding:.5rem 1rem; }}
</style></head><body><main>
<h1>Monitorage du service d'IA – VeilleIA</h1>
<p>Fenêtre de surveillance : {details['fenetre_jours']} derniers jours. Généré le {datetime.now(UTC):%d/%m/%Y à %H:%M} UTC.</p>
<section class="encadre"><h2>Alertes</h2>{bloc_alertes}</section>
<h2>Indicateurs</h2>
<table><caption>Indicateurs du service et seuils d'alerte</caption>
<thead><tr><th scope="col">Indicateur</th><th scope="col">Valeur</th><th scope="col">Seuil</th><th scope="col">État</th></tr></thead>
<tbody>{lignes}</tbody></table>
<h2>Détail par modèle</h2>
<table><caption>Appels par fournisseur et modèle</caption>
<thead><tr><th scope="col">Modèle</th><th scope="col">Appels</th><th scope="col">Succès</th>
<th scope="col">Latence moyenne (s)</th><th scope="col">Tokens</th></tr></thead><tbody>{modeles}</tbody></table>
<h2>Dernières erreurs</h2><ul>{erreurs}</ul>
</main></body></html>
"""


def produire_rapport(config: Config, stockage: Stockage) -> tuple[list[str], Path]:
    indicateurs, details = calculer_indicateurs(config, stockage)
    alertes = verifier_alertes(indicateurs)
    dossier = config.chemin(config.monitorage["dossier_sortie"])
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / "tableau_de_bord.html"
    chemin.write_text(rendre_tableau_de_bord(indicateurs, details, alertes), encoding="utf-8")
    (dossier / "indicateurs.json").write_text(json.dumps({
        "genere_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "indicateurs": [{"nom": i.nom, "valeur": i.valeur, "seuil": i.seuil, "alerte": i.en_alerte}
                        for i in indicateurs],
        "alertes": alertes, **details,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return alertes, chemin
