"""Analyse des articles collectés par le service d'IA (F1 à F4)."""

from __future__ import annotations

import logging
import time

from .config import Config
from .ia_client import ClientIA, ErreurServiceIA
from .prompts import messages_analyse
from .schemas import AnalyseArticle
from .stockage import Stockage

log = logging.getLogger("veilleia.analyse")


def analyser_article(client: ClientIA, config: Config, titre: str, source: str, contenu: str,
                     tache: str = "analyse") -> AnalyseArticle:
    prod = config.production
    return client.completer_json(
        messages_analyse(config.themes, titre, source, contenu),
        AnalyseArticle,
        modele=prod["modele_analyse"],
        max_tokens=prod["max_tokens_analyse"],
        temperature=prod["temperature"],
        tache=tache,
    )


def analyser_en_attente(client: ClientIA, config: Config, stockage: Stockage,
                        limite: int | None = None) -> dict[str, int]:
    """Analyse uniquement les articles jamais analysés (pas de double facturation, sobriété)."""
    bilan = {"analyses": 0, "erreurs": 0}
    pause = config.production.get("pause_entre_appels_s", 0)
    a_traiter = stockage.articles_a_analyser(limite)
    log.info("%d article(s) à analyser avec %s", len(a_traiter), client.fournisseur.libelle)
    for i, art in enumerate(a_traiter, start=1):
        try:
            resultat = analyser_article(client, config, art["titre"], art["source_id"], art["contenu"])
            stockage.enregistrer_analyse(
                art["id"], resultat.model_dump(),
                analyse_par=f"{client.fournisseur.id}/{client.fournisseur.modele(config.production['modele_analyse'])}",
            )
            bilan["analyses"] += 1
            log.info("[%d/%d] %-13s %d/5  %s", i, len(a_traiter), resultat.categorie, resultat.pertinence,
                     art["titre"][:70])
        except ErreurServiceIA as exc:
            stockage.enregistrer_erreur_analyse(art["id"], str(exc))
            bilan["erreurs"] += 1
            log.warning("[%d/%d] échec : %s", i, len(a_traiter), exc)
            if exc.code_http in (401, 403):
                log.error("Accès refusé : vérifier la clé API. Arrêt de l'analyse.")
                break
        if pause:
            time.sleep(pause)
    return bilan
