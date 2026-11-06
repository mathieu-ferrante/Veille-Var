"""Chargement de la configuration (config.yaml) et des secrets (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent


class ErreurConfiguration(Exception):
    """Configuration absente ou incohérente."""


@dataclass
class Fournisseur:
    """Un service d'IA accessible via une API compatible « chat completions »."""

    id: str
    libelle: str
    base_url: str
    cle_env: str | None
    json_mode: bool
    modeles: dict[str, str]
    prix: dict[str, dict[str, float | None]] = field(default_factory=dict)
    parametre_max_tokens: str = "max_tokens"
    temperature_supportee: bool = True
    requetes_par_minute: int | None = None  # limite de débit de l'offre souscrite (None = pas de limite)

    @property
    def cle_api(self) -> str | None:
        return os.getenv(self.cle_env) if self.cle_env else None

    def est_configure(self) -> bool:
        """Vrai si le fournisseur peut être appelé (clé présente ou pas de clé requise)."""
        return self.cle_env is None or bool(self.cle_api)

    def modele(self, taille_ou_nom: str) -> str:
        """Accepte « petit » / « grand » ou directement un nom de modèle."""
        return self.modeles.get(taille_ou_nom, taille_ou_nom)

    def prix_modele(self, modele: str) -> tuple[float | None, float | None]:
        p = self.prix.get(modele) or {}
        return p.get("entree"), p.get("sortie")


@dataclass
class Config:
    brut: dict[str, Any]
    racine: Path

    # --- accès pratiques ---------------------------------------------------
    @property
    def production(self) -> dict[str, Any]:
        return self.brut["production"]

    @property
    def collecte(self) -> dict[str, Any]:
        return self.brut["collecte"]

    @property
    def synthese(self) -> dict[str, Any]:
        return self.brut["synthese"]

    @property
    def monitorage(self) -> dict[str, Any]:
        return self.brut["monitorage"]

    @property
    def themes(self) -> str:
        return self.brut.get("themes_collectivite", "").strip()

    @property
    def chemin_bdd(self) -> Path:
        return self.racine / self.brut.get("base_de_donnees", "data/veilleia.db")

    def chemin(self, relatif: str) -> Path:
        return self.racine / relatif

    def fournisseur(self, ident: str | None = None) -> Fournisseur:
        ident = ident or self.production["fournisseur"]
        conf = self.brut["fournisseurs"].get(ident)
        if conf is None:
            raise ErreurConfiguration(f"Fournisseur inconnu : {ident!r}")
        base_url = os.getenv(conf["base_url_env"]) if conf.get("base_url_env") else None
        return Fournisseur(
            id=ident,
            libelle=conf.get("libelle", ident),
            base_url=(base_url or conf["base_url"]).rstrip("/"),
            cle_env=conf.get("cle_env"),
            json_mode=bool(conf.get("json_mode", True)),
            modeles=conf.get("modeles", {}),
            prix=conf.get("prix") or {},
            parametre_max_tokens=conf.get("parametre_max_tokens", "max_tokens"),
            temperature_supportee=bool(conf.get("temperature_supportee", True)),
            requetes_par_minute=conf.get("requetes_par_minute"),
        )

    def fournisseurs(self) -> list[Fournisseur]:
        return [self.fournisseur(i) for i in self.brut["fournisseurs"]]


def charger_config(chemin: str | Path | None = None) -> Config:
    """Charge config.yaml (et .env s'il existe) depuis la racine du projet."""
    chemin = Path(chemin) if chemin else RACINE / "config.yaml"
    if not chemin.exists():
        raise ErreurConfiguration(f"Fichier de configuration introuvable : {chemin}")
    racine = chemin.resolve().parent
    load_dotenv(racine / ".env", override=False)
    with chemin.open(encoding="utf-8") as f:
        brut = yaml.safe_load(f)
    for section in ("fournisseurs", "production", "collecte", "synthese", "monitorage"):
        if section not in brut:
            raise ErreurConfiguration(f"Section manquante dans {chemin.name} : {section}")
    return Config(brut=brut, racine=racine)
