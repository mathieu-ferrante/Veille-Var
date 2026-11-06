import json

import httpx
import pytest

from veilleia.ia_client import ClientIA, ErreurServiceIA, texte_reponse
from veilleia.schemas import AnalyseArticle

from .conftest import ANALYSE_VALIDE, reponse_chat


def _appels(stockage):
    return [dict(r) for r in stockage.cnx.execute("SELECT * FROM appels_ia")]


def test_cle_absente_refusee(config, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY")
    with pytest.raises(ErreurServiceIA, match="MISTRAL_API_KEY"):
        ClientIA(config.fournisseur("mistral"))


def test_requete_conforme_et_authentifiee(fabrique_client):
    client, requetes = fabrique_client([reponse_chat(ANALYSE_VALIDE)])
    client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit", max_tokens=300)
    req = requetes[0]
    corps = json.loads(req.content)
    assert req.url == "https://api.eu.mistral.ai/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer cle-de-test"
    assert corps["model"] == "ministral-8b-latest"
    assert corps["response_format"] == {"type": "json_object"}
    assert corps["temperature"] == 0.1 and corps["max_tokens"] == 300


def test_appel_reussi_journalise(fabrique_client, stockage):
    client, _ = fabrique_client([reponse_chat(ANALYSE_VALIDE, tokens=(120, 60))])
    resultat = client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit")
    assert resultat.pertinence == 5
    (appel,) = _appels(stockage)
    assert appel["statut"] == "ok" and appel["json_valide"] == 1
    assert (appel["tokens_entree"], appel["tokens_sortie"]) == (120, 60)
    assert appel["latence_s"] is not None


def test_nouvelle_tentative_sur_429(fabrique_client, stockage):
    client, requetes = fabrique_client([httpx.Response(429), httpx.Response(503), reponse_chat(ANALYSE_VALIDE)])
    client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit")
    assert len(requetes) == 3
    assert _appels(stockage)[0]["tentatives"] == 3


def test_erreur_401_sans_nouvelle_tentative(fabrique_client, stockage):
    client, requetes = fabrique_client([httpx.Response(401, json={"message": "Unauthorized"})])
    with pytest.raises(ErreurServiceIA) as exc:
        client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit")
    assert exc.value.code_http == 401 and len(requetes) == 1
    assert _appels(stockage)[0]["statut"] == "erreur"


def test_json_non_conforme_journalise(fabrique_client, stockage):
    client, _ = fabrique_client([reponse_chat({"categorie": "sport", "pertinence": 9})])
    with pytest.raises(ErreurServiceIA, match="non conforme"):
        client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit")
    assert _appels(stockage)[0]["json_valide"] == 0


def test_secret_jamais_journalise(fabrique_client, stockage):
    client, _ = fabrique_client([httpx.Response(400, text="clé invalide : sk-abcdefghijklmnop")])
    with pytest.raises(ErreurServiceIA) as exc:
        client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit")
    assert "sk-abcdefghijklmnop" not in str(exc.value)
    assert "sk-abcdefghijklmnop" not in (_appels(stockage)[0]["erreur"] or "")


def test_cout_calcule_si_prix_renseignes(fabrique_client, stockage):
    client, _ = fabrique_client([reponse_chat(ANALYSE_VALIDE, tokens=(1_000_000, 500_000),
                                              modele="mistral-small-latest")])
    client.fournisseur.prix = {"mistral-small-latest": {"entree": 0.2, "sortie": 0.6}}
    client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit")
    assert _appels(stockage)[0]["cout_eur"] == pytest.approx(0.5)


def test_parametres_specifiques_openai(config, monkeypatch, stockage):
    monkeypatch.setenv("OPENAI_API_KEY", "cle")
    requetes = []

    def gestionnaire(req):
        requetes.append(json.loads(req.content))
        return httpx.Response(200, json=reponse_chat(ANALYSE_VALIDE))

    client = ClientIA(config.fournisseur("openai"), stockage,
                      client_http=httpx.Client(transport=httpx.MockTransport(gestionnaire)))
    client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, modele="petit", max_tokens=50)
    assert "max_completion_tokens" in requetes[0] and "temperature" not in requetes[0]


def test_texte_reponse_modele_a_raisonnement():
    # Format des modèles « à raisonnement » : le raisonnement est ignoré, seul le texte compte.
    blocs = [{"type": "thinking", "thinking": [{"type": "text", "text": "je réfléchis"}]},
             {"type": "text", "text": "OK"}]
    assert texte_reponse(blocs) == "OK"
    assert texte_reponse("OK") == "OK"
    assert texte_reponse(None) == ""