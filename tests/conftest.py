"""Fixtures communes. Les tests n'appellent jamais un vrai service d'IA ni Internet :
les réponses HTTP sont simulées avec httpx.MockTransport."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from veilleia.config import Config, charger_config
from veilleia.ia_client import ClientIA
from veilleia.stockage import Stockage

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    for nom in ("config.yaml", "sources.yaml"):
        shutil.copy(RACINE / nom, tmp_path / nom)
    for var in ("MISTRAL_API_KEY", "OPENAI_API_KEY", "ALBERT_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MISTRAL_API_KEY", "cle-de-test")
    return charger_config(tmp_path / "config.yaml")


@pytest.fixture
def stockage() -> Stockage:
    s = Stockage(":memory:")
    yield s
    s.fermer()


def reponse_chat(contenu: str | dict, tokens: tuple[int, int] = (100, 50), modele: str = "modele-test") -> dict:
    texte = contenu if isinstance(contenu, str) else json.dumps(contenu, ensure_ascii=False)
    return {
        "model": modele,
        "choices": [{"message": {"role": "assistant", "content": texte}}],
        "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]},
    }


ANALYSE_VALIDE = {
    "categorie": "reglementaire",
    "pertinence": 5,
    "resume": "La CNIL publie des recommandations sur l'usage de l'IA générative par les collectivités.",
    "mots_cles": ["CNIL", "IA générative", "collectivités"],
    "entites": [{"type": "organisation", "valeur": "CNIL"}],
}


@pytest.fixture
def fabrique_client(config: Config, stockage: Stockage) -> Callable[..., tuple[ClientIA, list[httpx.Request]]]:
    """Crée un ClientIA branché sur un faux serveur. `reponses` : liste de httpx.Response ou de dict."""

    def fabriquer(reponses: list, fournisseur: str = "mistral") -> tuple[ClientIA, list[httpx.Request]]:
        requetes: list[httpx.Request] = []
        file = list(reponses)

        def gestionnaire(requete: httpx.Request) -> httpx.Response:
            requetes.append(requete)
            r = file.pop(0) if len(file) > 1 else file[0]
            return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

        http = httpx.Client(transport=httpx.MockTransport(gestionnaire))
        client = ClientIA(config.fournisseur(fournisseur), stockage, tentatives=3, client_http=http,
                          attente_base_s=0)
        return client, requetes

    return fabriquer
