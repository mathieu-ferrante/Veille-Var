"""Connecteur au service d'IA (compétence C8).

Un seul connecteur pour tous les fournisseurs : ils exposent tous l'interface
« chat completions » compatible OpenAI (Mistral, Albert, OpenAI, Gemini,
Anthropic, Ollama). Le connecteur gère :
  - l'authentification (clé API lue dans l'environnement, jamais journalisée) ;
  - le délai d'attente et les nouvelles tentatives (429, 5xx, erreurs réseau) ;
  - la validation des réponses JSON par un schéma ;
  - le monitorage : chaque appel est enregistré (latence, tokens, coût, statut).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import Fournisseur
from .journal import masquer_secrets
from .schemas import ErreurJSON, extraire_json
from .stockage import Stockage

log = logging.getLogger("veilleia.ia")

M = TypeVar("M", bound=BaseModel)

CODES_A_REESSAYER = {408, 409, 425, 429, 500, 502, 503, 504}


class ErreurServiceIA(Exception):
    """Échec définitif d'un appel au service d'IA."""

    def __init__(self, message: str, code_http: int | None = None) -> None:
        super().__init__(message)
        self.code_http = code_http


def texte_reponse(contenu) -> str:
    """Extrait le texte de la réponse.

    La plupart des services renvoient une chaîne. Les modèles « à raisonnement » (ex. mistral-large-4)
    renvoient une liste de blocs : on ne garde que les blocs de type « text », jamais le raisonnement.
    """
    if contenu is None:
        return ""
    if isinstance(contenu, str):
        return contenu
    return "".join(b.get("text", "") for b in contenu if isinstance(b, dict) and b.get("type") == "text")


@dataclass
class ReponseIA:
    texte: str
    modele: str
    tokens_entree: int | None
    tokens_sortie: int | None
    latence_s: float
    tentatives: int
    code_http: int


class ClientIA:
    def __init__(
        self,
        fournisseur: Fournisseur,
        stockage: Stockage | None = None,
        timeout_s: float = 60,
        tentatives: int = 3,
        client_http: httpx.Client | None = None,
        attente_base_s: float = 1.0,
    ) -> None:
        if not fournisseur.est_configure():
            raise ErreurServiceIA(
                f"Clé API absente pour {fournisseur.libelle} : renseigner {fournisseur.cle_env} dans .env"
            )
        self.fournisseur = fournisseur
        self.stockage = stockage
        self.tentatives = max(1, tentatives)
        self.attente_base_s = attente_base_s
        entetes = {"Content-Type": "application/json"}
        if fournisseur.cle_api:
            entetes["Authorization"] = f"Bearer {fournisseur.cle_api}"
        self.http = client_http or httpx.Client(timeout=timeout_s)
        self.http.headers.update(entetes)

    def fermer(self) -> None:
        self.http.close()

    # ------------------------------------------------------------------
    def completer(
        self,
        messages: list[dict[str, str]],
        modele: str,
        max_tokens: int = 500,
        temperature: float = 0.1,
        json_attendu: bool = True,
        tache: str = "analyse",
    ) -> ReponseIA:
        """Envoie une requête de complétion, avec nouvelles tentatives. Lève ErreurServiceIA si échec."""
        f = self.fournisseur
        nom_modele = f.modele(modele)
        corps: dict[str, Any] = {"model": nom_modele, "messages": messages, f.parametre_max_tokens: max_tokens}
        if f.temperature_supportee:
            corps["temperature"] = temperature
        if json_attendu and f.json_mode:
            corps["response_format"] = {"type": "json_object"}

        url = f"{f.base_url}/chat/completions"
        derniere_erreur, code = "", None
        debut = time.perf_counter()
        for essai in range(1, self.tentatives + 1):
            try:
                r = self.http.post(url, json=corps)
                code = r.status_code
                if r.status_code in CODES_A_REESSAYER and essai < self.tentatives:
                    derniere_erreur = f"HTTP {r.status_code}"
                    self._patienter(essai, r.headers.get("retry-after"))
                    continue
                if r.status_code >= 400:
                    raise ErreurServiceIA(f"HTTP {r.status_code} : {masquer_secrets(r.text[:300])}", r.status_code)
                donnees = r.json()
                latence = time.perf_counter() - debut
                usage = donnees.get("usage") or {}
                texte = texte_reponse(donnees["choices"][0]["message"].get("content"))
                return ReponseIA(
                    texte=texte,
                    modele=donnees.get("model", nom_modele),
                    tokens_entree=usage.get("prompt_tokens"),
                    tokens_sortie=usage.get("completion_tokens"),
                    latence_s=latence,
                    tentatives=essai,
                    code_http=r.status_code,
                )
            except httpx.TransportError as exc:  # réseau, délai dépassé
                derniere_erreur = f"{type(exc).__name__}: {exc}"
                if essai < self.tentatives:
                    self._patienter(essai, None)
                    continue
            except (KeyError, IndexError, ValueError) as exc:
                raise ErreurServiceIA(f"Réponse inattendue du service : {exc}", code) from exc
        raise ErreurServiceIA(f"Échec après {self.tentatives} tentatives : {derniere_erreur}", code)

    def completer_json(
        self,
        messages: list[dict[str, str]],
        schema: type[M],
        modele: str,
        max_tokens: int = 500,
        temperature: float = 0.1,
        tache: str = "analyse",
    ) -> M:
        """Appel + extraction + validation du JSON. Tout appel est journalisé pour le monitorage."""
        nom_modele = self.fournisseur.modele(modele)
        debut = time.perf_counter()
        try:
            rep = self.completer(messages, modele, max_tokens, temperature, json_attendu=True, tache=tache)
        except ErreurServiceIA as exc:
            self._journaliser(tache, nom_modele, "erreur", exc.code_http, time.perf_counter() - debut,
                              None, None, None, self.tentatives, str(exc))
            raise
        try:
            resultat = schema.model_validate(extraire_json(rep.texte))
        except (ErreurJSON, ValidationError) as exc:
            self._journaliser(tache, rep.modele, "erreur", rep.code_http, rep.latence_s, rep.tokens_entree,
                              rep.tokens_sortie, False, rep.tentatives, f"JSON invalide : {exc}"[:300])
            raise ErreurServiceIA(f"Réponse non conforme au schéma {schema.__name__} : {exc}") from exc
        self._journaliser(tache, rep.modele, "ok", rep.code_http, rep.latence_s, rep.tokens_entree,
                          rep.tokens_sortie, True, rep.tentatives, None)
        return resultat

    def verifier_acces(self, modele: str = "petit") -> ReponseIA:
        """Test de connexion minimal (utilisé par `veilleia verifier`)."""
        rep = self.completer([{"role": "user", "content": "Réponds uniquement : OK"}], modele,
                             max_tokens=300, json_attendu=False, tache="test")
        self._journaliser("test", rep.modele, "ok", rep.code_http, rep.latence_s, rep.tokens_entree,
                          rep.tokens_sortie, None, rep.tentatives, None)
        return rep

    # ------------------------------------------------------------------
    def cout_eur(self, modele: str, tokens_entree: int | None, tokens_sortie: int | None) -> float | None:
        prix_e, prix_s = self.fournisseur.prix_modele(modele)
        if prix_e is None or prix_s is None or tokens_entree is None or tokens_sortie is None:
            return None
        return round((tokens_entree * prix_e + tokens_sortie * prix_s) / 1_000_000, 6)

    def _patienter(self, essai: int, retry_after: str | None) -> None:
        try:
            attente = float(retry_after) if retry_after else self.attente_base_s * 2 ** (essai - 1)
        except ValueError:
            attente = self.attente_base_s * 2 ** (essai - 1)
        attente = min(attente, 30)
        log.warning("Service %s indisponible, nouvelle tentative dans %.1fs", self.fournisseur.id, attente)
        time.sleep(attente)

    def _journaliser(self, tache: str, modele: str, statut: str, code_http: int | None, latence: float | None,
                     t_entree: int | None, t_sortie: int | None, json_valide: bool | None, tentatives: int,
                     erreur: str | None) -> None:
        if self.stockage is None:
            return
        self.stockage.journaliser_appel(
            fournisseur=self.fournisseur.id,
            modele=modele,
            tache=tache,
            statut=statut,
            code_http=code_http,
            latence_s=round(latence, 3) if latence is not None else None,
            tokens_entree=t_entree,
            tokens_sortie=t_sortie,
            cout_eur=self.cout_eur(modele, t_entree, t_sortie),
            json_valide=None if json_valide is None else int(json_valide),
            tentatives=tentatives,
            erreur=masquer_secrets(erreur) if erreur else None,
        )
