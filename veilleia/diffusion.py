"""Diffusion de la synthèse par mail (facultatif, paramétré dans .env).

RGPD : les destinataires sont des listes de diffusion de service, lues dans .env,
jamais journalisées ni versionnées.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger("veilleia.diffusion")


def diffusion_configuree() -> bool:
    return all(os.getenv(v) for v in ("SMTP_HOST", "SMTP_FROM", "SMTP_TO"))


def envoyer_synthese(chemin_html: Path, chemin_md: Path, objet: str) -> bool:
    if not diffusion_configuree():
        log.info("Diffusion par mail non configurée (SMTP_* absents de .env) : étape ignorée.")
        return False
    msg = EmailMessage()
    msg["Subject"] = objet
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = os.environ["SMTP_TO"]
    # Version texte (Markdown lisible tel quel) + version HTML accessible
    msg.set_content(chemin_md.read_text(encoding="utf-8"))
    msg.add_alternative(chemin_html.read_text(encoding="utf-8"), subtype="html")
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=30) as smtp:
        smtp.starttls()
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
    nb = len([d for d in os.environ["SMTP_TO"].split(",") if d.strip()])
    log.info("Synthèse envoyée à %d liste(s) de diffusion.", nb)
    return True
