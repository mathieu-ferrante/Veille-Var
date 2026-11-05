"""Journalisation : console lisible + fichier JSON Lines exploitable par le monitorage.

Règle RGPD : on ne journalise jamais de donnée personnelle (pas de destinataires
de mails, pas de clé API, pas de contenu complet d'article).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

_MOTIF_SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+|api[_-]?key=\S+)", re.IGNORECASE)


def masquer_secrets(texte: str) -> str:
    """Remplace tout ce qui ressemble à une clé API par ***."""
    return _MOTIF_SECRET.sub("***", texte)


class FormatJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        donnees = {
            "horodatage": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "niveau": record.levelname,
            "module": record.name,
            "message": masquer_secrets(record.getMessage()),
        }
        extra = getattr(record, "donnees", None)
        if extra:
            donnees["donnees"] = extra
        return json.dumps(donnees, ensure_ascii=False)


def configurer_journal(dossier: Path, niveau: int = logging.INFO) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    racine = logging.getLogger("veilleia")
    if racine.handlers:
        return
    racine.setLevel(niveau)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    racine.addHandler(console)

    fichier = logging.FileHandler(dossier / "veilleia.jsonl", encoding="utf-8")
    fichier.setFormatter(FormatJSON())
    racine.addHandler(fichier)
