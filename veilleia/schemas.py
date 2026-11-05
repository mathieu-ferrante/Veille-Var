"""Schémas de validation des réponses du service d'IA (sorties structurées JSON)."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CATEGORIES = ("technique", "reglementaire", "offre_outil", "hors_sujet")
TYPES_ENTITE = ("modele_ia", "organisation", "texte_juridique", "date", "autre")


class Entite(BaseModel):
    type: Literal["modele_ia", "organisation", "texte_juridique", "date", "autre"]
    valeur: str = Field(min_length=1, max_length=120)


class AnalyseArticle(BaseModel):
    """F1 à F4 : classement, pertinence, résumé, mots-clés et entités."""

    categorie: Literal["technique", "reglementaire", "offre_outil", "hors_sujet"]
    pertinence: int = Field(ge=1, le=5)
    resume: str = Field(min_length=10, max_length=700)
    mots_cles: list[str] = Field(default_factory=list, max_length=8)
    entites: list[Entite] = Field(default_factory=list, max_length=12)

    @field_validator("categorie", mode="before")
    @classmethod
    def normaliser_categorie(cls, v: str) -> str:
        v = str(v).strip().lower().replace("é", "e").replace(" ", "_").replace("-", "_")
        return {"reglementation": "reglementaire", "offre": "offre_outil", "outil": "offre_outil",
                "hors_theme": "hors_sujet"}.get(v, v)

    @field_validator("mots_cles")
    @classmethod
    def nettoyer_mots_cles(cls, v: list[str]) -> list[str]:
        return [m.strip()[:60] for m in v if m and m.strip()]


class PointCle(BaseModel):
    titre: str = Field(min_length=3, max_length=160)
    texte: str = Field(min_length=10, max_length=900)
    references: list[int] = Field(min_length=1, description="Numéros des articles sources")


class SectionSynthese(BaseModel):
    theme: Literal["Réglementation", "Technique", "Offres et outils", "Sécurité"]
    points: list[PointCle] = Field(min_length=1)


class SyntheseHebdo(BaseModel):
    """F5 : synthèse hebdomadaire."""

    chapeau: str = Field(min_length=20, max_length=900)
    sections: list[SectionSynthese] = Field(min_length=1)
    a_retenir: list[str] = Field(default_factory=list, max_length=6,
                                 description="Actions ou points d'attention pour le Département")


class ErreurJSON(ValueError):
    """La réponse du modèle n'est pas un JSON exploitable."""


_BLOC_CODE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extraire_json(texte: str) -> dict:
    """Extrait le premier objet JSON d'une réponse (tolère les blocs ```json```)."""
    if not texte or not texte.strip():
        raise ErreurJSON("Réponse vide")
    m = _BLOC_CODE.search(texte)
    candidat = m.group(1) if m else texte
    debut, fin = candidat.find("{"), candidat.rfind("}")
    if debut == -1 or fin <= debut:
        raise ErreurJSON("Aucun objet JSON trouvé")
    try:
        return json.loads(candidat[debut:fin + 1])
    except json.JSONDecodeError as exc:
        raise ErreurJSON(f"JSON mal formé : {exc}") from exc
