"""Diffusion de la synthèse par mail (facultatif, paramétré dans .env).

RGPD : les destinataires sont des listes de diffusion de service, lues dans .env,
jamais journalisées ni versionnées.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger("veilleia.diffusion")


def diffusion_configuree() -> bool:
    return all(os.getenv(v) for v in ("SMTP_HOST", "SMTP_FROM", "SMTP_TO"))


def envoyer_synthese(chemin_html: Path, chemin_md: Path, objet: str) -> bool:
    """Envoie la synthèse. Renvoie False (sans lever d'exception) si l'envoi est impossible :
    la synthèse reste écrite sur disque et la chaîne hebdomadaire continue."""
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
    # Chiffrement avec vérification du certificat et du nom du serveur (évite l'interception des identifiants)
    contexte = ssl.create_default_context()
    hote, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    utilisateur, mot_de_passe = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    if utilisateur and not mot_de_passe:
        log.error("SMTP_USER est renseigné sans SMTP_PASSWORD : synthèse non envoyée.")
        return False
    try:
        if port == 465:  # SMTPS : chiffrement dès la connexion
            connexion = smtplib.SMTP_SSL(hote, port, timeout=30, context=contexte)
        else:  # 587 : connexion puis STARTTLS
            connexion = smtplib.SMTP(hote, port, timeout=30)
        with connexion as smtp:
            if port != 465:
                smtp.starttls(context=contexte)
            if utilisateur:
                smtp.login(utilisateur, mot_de_passe)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Envoi de la synthèse impossible (%s : %s). Elle reste disponible dans syntheses/.",
                  type(exc).__name__, exc)
        return False
    nb = len([d for d in os.environ["SMTP_TO"].split(",") if d.strip()])
    log.info("Synthèse envoyée à %d liste(s) de diffusion.", nb)
    return True
