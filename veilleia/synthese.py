"""Synthèse hebdomadaire (F5) : génération par le service d'IA puis rendu accessible HTML + Markdown.

Accessibilité (RGAA / recommandations Valentin Haüy, AcceDe) appliquée au rendu HTML :
  - langue déclarée (lang="fr"), titre de page explicite, lien d'évitement ;
  - hiérarchie de titres stricte (h1 > h2 > h3), listes structurées ;
  - liens explicites (intitulé de la publication + source), jamais « cliquez ici » ;
  - contrastes AA, police lisible, taille relative, pas d'information portée par la couleur seule ;
  - tableau des sources avec <caption> et en-têtes <th scope> ;
  - mention de transparence : contenu généré par IA et relu par un agent (AI Act).
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .collecte import url_web
from .config import Config
from .ia_client import ClientIA
from .prompts import messages_synthese
from .schemas import SyntheseHebdo
from .stockage import Stockage

log = logging.getLogger("veilleia.synthese")

LIBELLES_CATEGORIE = {
    "reglementaire": "Réglementaire",
    "technique": "Technique",
    "offre_outil": "Offre ou outil",
    "hors_sujet": "Hors sujet",
}


@dataclass
class ResultatSynthese:
    synthese: SyntheseHebdo
    articles: list[dict[str, Any]]
    debut: datetime
    fin: datetime
    fournisseur: str
    modele: str


def periode_par_defaut(fin: datetime | None = None, jours: int = 7) -> tuple[datetime, datetime]:
    fin = fin or datetime.now(UTC)
    return fin - timedelta(days=jours), fin


def _fr(d: datetime) -> str:
    d = d.astimezone()  # stockage en UTC, affichage à l'heure locale (Paris)
    mois =["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
            "octobre", "novembre", "décembre"]
    return f"{d.day} {mois[d.month - 1]} {d.year}"


def generer_synthese(client: ClientIA, config: Config, stockage: Stockage,
                     debut: datetime, fin: datetime) -> ResultatSynthese | None:
    conf = config.synthese
    lignes = stockage.articles_pour_synthese(
        debut.isoformat(timespec="seconds"), fin.isoformat(timespec="seconds"),
        conf["pertinence_min"], conf["max_articles"],
    )
    articles = [dict(r) for r in lignes]
    if not articles:
        log.warning("Aucun article analysé et pertinent sur la période : pas de synthèse.")
        return None
    periode = f"du {_fr(debut)} au {_fr(fin)}"
    log.info("Synthèse de %d article(s) %s", len(articles), periode)
    prod = config.production
    synthese = client.completer_json(
        messages_synthese(articles, periode), SyntheseHebdo,
        modele=prod["modele_synthese"], max_tokens=prod["max_tokens_synthese"],
        temperature=prod["temperature"], tache="synthese",
    )
    # On écarte les références hors limites ou en double (le modèle ne doit citer que les articles fournis).
    # Un point qui ne cite plus aucune publication est retiré : toute information diffusée doit être sourcée.
    for section in synthese.sections:
        for point in section.points:
            point.references = list(dict.fromkeys(r for r in point.references if 1 <= r <= len(articles)))
        retires = [p.titre for p in section.points if not p.references]
        if retires:
            log.warning("Point(s) retiré(s) faute de source valide : %s", " ; ".join(retires))
        section.points = [p for p in section.points if p.references]
    synthese.sections = [s for s in synthese.sections if s.points]
    return ResultatSynthese(synthese, articles, debut, fin, client.fournisseur.libelle,
                            client.fournisseur.modele(prod["modele_synthese"]))


# ---------------------------------------------------------------------------
# Rendus
# ---------------------------------------------------------------------------
CSS = """
:root { --texte:#1a1a1a; --fond:#ffffff; --accent:#00436e; --doux:#4a4a4a; --bord:#c8d3dc; --zone:#eef3f7; }
@media (prefers-color-scheme: dark) {
  :root { --texte:#f0f0f0; --fond:#121417; --accent:#8cc8ff; --doux:#c4c4c4; --bord:#3a4550; --zone:#1d242b; }
}
* { box-sizing: border-box; }
body { margin:0; font-family: Arial, Helvetica, sans-serif; font-size:1rem; line-height:1.6;
       color:var(--texte); background:var(--fond); }
main, header, footer { max-width: 50rem; margin: 0 auto; padding: 0 1rem; }
a { color: var(--accent); text-decoration: underline; }
a:focus, a:hover { outline: 3px solid var(--accent); outline-offset: 2px; }
.evitement { position:absolute; left:-999px; }
.evitement:focus { position:static; display:inline-block; padding:.5rem; background:var(--zone); }
h1 { color:var(--accent); font-size:1.8rem; line-height:1.25; }
h2 { color:var(--accent); font-size:1.4rem; border-bottom:2px solid var(--bord); padding-bottom:.25rem; margin-top:2rem; }
h3 { font-size:1.1rem; margin-bottom:.25rem; }
.meta, .sources-point { color:var(--doux); font-size:.95rem; }
.encadre { background:var(--zone); border-left:6px solid var(--accent); padding:.75rem 1rem; margin:1rem 0; }
table { border-collapse:collapse; width:100%; font-size:.95rem; }
caption { text-align:left; font-weight:bold; padding:.5rem 0; }
th, td { border:1px solid var(--bord); padding:.4rem .5rem; text-align:left; vertical-align:top; }
th { background:var(--zone); }
@media print { a { color: inherit; } .evitement { display:none; } }
"""


def _lien_article(a: dict[str, Any], numero: int) -> str:
    meta = f'<span class="meta">({html.escape(a["source_id"])}, référence {numero})</span>'
    if not url_web(a["url"]):  # deuxième barrière : jamais de lien « javascript: » dans un mail
        return f"{html.escape(a['titre'])} {meta}"
    return f'<a href="{html.escape(a["url"], quote=True)}">{html.escape(a["titre"])}</a> {meta}'


def _lien_md(titre: str, url: str) -> str:
    """Lien Markdown robuste : crochets du titre et parenthèses de l'URL échappés."""
    titre = titre.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")
    if not url_web(url):
        return titre
    return f"[{titre}]({url.replace(' ', '%20').replace('(', '%28').replace(')', '%29')})"


def rendre_html(r: ResultatSynthese, relecteur: str) -> str:
    e = html.escape
    titre = f"Veille IA – semaine du {_fr(r.debut)} au {_fr(r.fin)}"
    sections = []
    for s in r.synthese.sections:
        points = []
        for p in s.points:
            refs = "".join(f"<li>{_lien_article(r.articles[n - 1], n)}</li>" for n in p.references)
            sources = f'\n<p class="sources-point">Sources :</p>\n<ul class="sources-point">{refs}</ul>' if refs else ""
            points.append(f"<h3>{e(p.titre)}</h3>\n<p>{e(p.texte)}</p>{sources}")
        sections.append(f"<section>\n<h2>{e(s.theme)}</h2>\n" + "\n".join(points) + "\n</section>")

    a_retenir = ""
    if r.synthese.a_retenir:
        items = "".join(f"<li>{e(x)}</li>" for x in r.synthese.a_retenir)
        a_retenir = f'<section class="encadre">\n<h2>À retenir pour le Département</h2>\n<ul>{items}</ul>\n</section>'

    lignes_tab = "".join(
        f"<tr><td>{i}</td><th scope=\"row\">{_lien_article(a, i)}</th>"
        f"<td>{e(LIBELLES_CATEGORIE.get(a['categorie'], a['categorie']))}</td>"
        f"<td>{a['pertinence']} sur 5</td></tr>"
        for i, a in enumerate(r.articles, start=1)
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre)} – DSI Département</title>
<style>{CSS}</style>
</head>
<body>
<a class="evitement" href="#contenu">Aller au contenu</a>
<header>
<p class="meta">Direction des systèmes d'information – Veille technique et réglementaire sur l'IA</p>
<h1>{e(titre)}</h1>
</header>
<main id="contenu">
<p>{e(r.synthese.chapeau)}</p>
{a_retenir}
{chr(10).join(sections)}
<section>
<h2>Publications analysées</h2>
<table>
<caption>Liste des {len(r.articles)} publications retenues, avec leur catégorie et leur pertinence</caption>
<thead><tr><th scope="col">N°</th><th scope="col">Publication</th><th scope="col">Catégorie</th>
<th scope="col">Pertinence</th></tr></thead>
<tbody>{lignes_tab}</tbody>
</table>
</section>
</main>
<footer>
<p class="encadre"><strong>Transparence :</strong> cette synthèse a été générée automatiquement par un service
d'intelligence artificielle ({e(r.fournisseur)}, modèle {e(r.modele)}) à partir de sources publiques, puis relue par
{e(relecteur)}. Vérifiez toujours l'information dans la source d'origine avant toute décision.</p>
<p class="meta">Générée le {_fr(datetime.now(UTC))}.</p>
</footer>
</body>
</html>
"""


def rendre_markdown(r: ResultatSynthese, relecteur: str) -> str:
    lignes = [f"# Veille IA – semaine du {_fr(r.debut)} au {_fr(r.fin)}", "", r.synthese.chapeau, ""]
    if r.synthese.a_retenir:
        lignes += ["## À retenir pour le Département", ""] + [f"- {x}" for x in r.synthese.a_retenir] + [""]
    for s in r.synthese.sections:
        lignes += [f"## {s.theme}", ""]
        for p in s.points:
            refs = ", ".join(_lien_md(r.articles[n - 1]["titre"], r.articles[n - 1]["url"]) for n in p.references)
            lignes += [f"### {p.titre}", "", p.texte, ""] + ([f"Sources : {refs}", ""] if refs else [])
    lignes += ["## Publications analysées", "", "| N° | Publication | Catégorie | Pertinence |",
               "|---|---|---|---|"]
    for i, a in enumerate(r.articles, start=1):
        lignes.append(f"| {i} | {_lien_md(a['titre'], a['url'])} ({a['source_id']}) | "
                      f"{LIBELLES_CATEGORIE.get(a['categorie'], a['categorie'])} | {a['pertinence']} sur 5 |")
    lignes += ["", f"> Transparence : synthèse générée par IA ({r.fournisseur}, modèle {r.modele}) à partir de "
               f"sources publiques, relue par {relecteur}."]
    return "\n".join(lignes) + "\n"


def ecrire_synthese(r: ResultatSynthese, config: Config, stockage: Stockage) -> tuple[Path, Path]:
    dossier = config.chemin(config.synthese["dossier_sortie"])
    dossier.mkdir(parents=True, exist_ok=True)
    base = f"veille_{r.fin.astimezone():%Y-%m-%d}"
    relecteur = config.synthese.get("relecteur", "un agent de la DSI")
    chemin_html, chemin_md = dossier / f"{base}.html", dossier / f"{base}.md"
    chemin_html.write_text(rendre_html(r, relecteur), encoding="utf-8")
    chemin_md.write_text(rendre_markdown(r, relecteur), encoding="utf-8")
    stockage.journaliser_synthese(r.debut.isoformat(timespec="seconds"), r.fin.isoformat(timespec="seconds"),
                                  len(r.articles), str(chemin_html.name), str(chemin_md.name))
    log.info("Synthèse écrite : %s", chemin_html)
    return chemin_html, chemin_md
