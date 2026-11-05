"""Collecte des publications depuis les flux RSS/Atom des sources de veille."""

from __future__ import annotations

import calendar
import html
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import feedparser
import httpx
import yaml

from .stockage import Article, Stockage

log = logging.getLogger("veilleia.collecte")

_BALISES = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")


@dataclass
class Source:
    id: str
    nom: str
    url: str
    theme: str
    langue: str = "fr"
    fiabilite: int = 3
    active: bool = True


def charger_sources(chemin: Path) -> list[Source]:
    with chemin.open(encoding="utf-8") as f:
        donnees = yaml.safe_load(f) or {}
    sources = [Source(**s) for s in donnees.get("sources", [])]
    ids = [s.id for s in sources]
    doublons = {i for i in ids if ids.count(i) > 1}
    if doublons:
        raise ValueError(f"Identifiants de source en double : {sorted(doublons)}")
    return [s for s in sources if s.active]


def texte_brut(fragment: str) -> str:
    """Retire le HTML et normalise les espaces."""
    sans_balises = _BALISES.sub(" ", fragment or "")
    return _ESPACES.sub(" ", html.unescape(sans_balises)).strip()


_MOIS_FR = {m: i for i, m in enumerate(
    ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
     "novembre", "décembre"], start=1)}
_DATE_FR = re.compile(r"(\d{1,2})\s+(" + "|".join(_MOIS_FR) + r")\s+(\d{4})", re.IGNORECASE)


def date_francaise(texte: str) -> datetime | None:
    """Lit une date du type « Vendredi 30 octobre 2026 » (non reconnue par feedparser)."""
    m = _DATE_FR.search(texte or "")
    if not m:
        return None
    return datetime(int(m.group(3)), _MOIS_FR[m.group(2).lower()], int(m.group(1)), tzinfo=UTC)


def _date_entree(entree: feedparser.FeedParserDict) -> datetime | None:
    for cle in ("published_parsed", "updated_parsed"):
        t = entree.get(cle)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), UTC)
    return date_francaise(entree.get("published", "") or entree.get("updated", ""))


def _contenu_entree(entree: feedparser.FeedParserDict) -> str:
    if entree.get("content"):
        return " ".join(c.get("value", "") for c in entree["content"])
    return entree.get("summary", "") or entree.get("description", "")


def parser_flux(source: Source, contenu: bytes, jours_max: int, max_par_source: int,
                taille_max: int, maintenant: datetime | None = None) -> tuple[list[Article], int]:
    """Transforme un flux brut en articles récents. Renvoie (articles, nb_entrees_du_flux)."""
    maintenant = maintenant or datetime.now(UTC)
    limite = maintenant - timedelta(days=jours_max)
    flux = feedparser.parse(contenu)
    articles: list[Article] = []
    for entree in flux.entries:
        url = entree.get("link")
        titre = texte_brut(entree.get("title", ""))
        if not url or not titre:
            continue
        date = _date_entree(entree)
        if date and date < limite:
            continue  # trop ancien : on ne l'envoie pas au modèle (sobriété)
        articles.append(
            Article(
                source_id=source.id,
                titre=titre[:300],
                url=url,
                date_pub=(date or maintenant).isoformat(timespec="seconds"),
                contenu=texte_brut(_contenu_entree(entree))[:taille_max],
                langue=source.langue,
            )
        )
    articles.sort(key=lambda a: a.date_pub or "", reverse=True)
    return articles[:max_par_source], len(flux.entries)


def collecter(sources: list[Source], stockage: Stockage, conf_collecte: dict,
              client: httpx.Client | None = None) -> dict[str, int]:
    """Collecte toutes les sources et stocke les nouveaux articles. Ne s'arrête pas sur une source en erreur."""
    proprietaire = client is None
    client = client or httpx.Client(
        timeout=conf_collecte.get("timeout_s", 20),
        follow_redirects=True,
        headers={"User-Agent": conf_collecte.get("user_agent", "VeilleIA/0.1")},
    )
    bilan = {"sources_ok": 0, "sources_erreur": 0, "nouveaux": 0}
    try:
        for source in sources:
            try:
                reponse = client.get(source.url)
                reponse.raise_for_status()
                articles, nb_entrees = parser_flux(
                    source, reponse.content,
                    jours_max=conf_collecte.get("jours_max", 8),
                    max_par_source=conf_collecte.get("max_par_source", 30),
                    taille_max=conf_collecte.get("taille_max_contenu", 2500),
                )
                nouveaux = stockage.inserer_articles(articles)
                stockage.journaliser_collecte(source.id, "ok", nb_entrees, nouveaux)
                bilan["sources_ok"] += 1
                bilan["nouveaux"] += nouveaux
                log.info("%-18s %3d récents, %3d nouveaux", source.id, len(articles), nouveaux)
            except (httpx.HTTPError, ValueError) as exc:
                stockage.journaliser_collecte(source.id, "erreur", erreur=f"{type(exc).__name__}: {exc}"[:300])
                bilan["sources_erreur"] += 1
                log.warning("%-18s ÉCHEC : %s", source.id, exc)
    finally:
        if proprietaire:
            client.close()
    return bilan
