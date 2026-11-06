"""Tests de la chaîne : analyse -> synthèse accessible -> monitorage -> benchmark."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from veilleia.analyse import analyser_en_attente
from veilleia.benchmark import charger_jeu_test, est_en_francais, evaluer_service
from veilleia.monitoring import calculer_indicateurs, verifier_alertes
from veilleia.stockage import Article
from veilleia.synthese import ecrire_synthese, generer_synthese

from .conftest import ANALYSE_VALIDE, reponse_chat

SYNTHESE = {
    "chapeau": "Semaine marquée par de nouvelles recommandations de la CNIL sur l'IA générative.",
    "sections": [{"theme": "Réglementation", "points": [
        {"titre": "Recommandations CNIL", "texte": "La CNIL précise les règles applicables aux collectivités.",
         "references": [1, 99]}]}],
    "a_retenir": ["Informer le DPO des nouvelles recommandations."],
}


def _articles(stockage, n=2):
    maintenant = datetime.now(UTC)
    stockage.inserer_articles([
        Article(source_id="cnil", titre=f"Publication {i}", url=f"https://exemple.fr/{i}",
                date_pub=(maintenant - timedelta(days=1)).isoformat(timespec="seconds"), contenu="Contenu")
        for i in range(n)
    ])


def test_analyse_puis_pas_de_double_traitement(config, stockage, fabrique_client):
    _articles(stockage)
    client, requetes = fabrique_client([reponse_chat(ANALYSE_VALIDE)])
    config.production["pause_entre_appels_s"] = 0
    assert analyser_en_attente(client, config, stockage) == {"analyses": 2, "erreurs": 0}
    assert analyser_en_attente(client, config, stockage) == {"analyses": 0, "erreurs": 0}
    assert len(requetes) == 2


def test_synthese_accessible(config, stockage, fabrique_client):
    _articles(stockage)
    config.production["pause_entre_appels_s"] = 0
    client, _ = fabrique_client([reponse_chat(ANALYSE_VALIDE)])
    analyser_en_attente(client, config, stockage)

    client, _ = fabrique_client([reponse_chat(SYNTHESE)])
    fin = datetime.now(UTC)
    resultat = generer_synthese(client, config, stockage, fin - timedelta(days=7), fin)
    assert resultat.synthese.sections[0].points[0].references == [1]  # référence 99 inexistante écartée

    html_path, md_path = ecrire_synthese(resultat, config, stockage)
    html = html_path.read_text(encoding="utf-8")
    assert '<html lang="fr">' in html
    assert html.count("<h1>") == 1 and "<h2>" in html and "<h3>" in html
    assert "<caption>" in html and 'scope="col"' in html
    assert 'href="#contenu"' in html  # lien d'évitement
    assert "Transparence" in html and "intelligence artificielle" in html
    assert "cliquez ici" not in html.lower()
    assert md_path.read_text(encoding="utf-8").startswith("# Veille IA")


def test_pas_de_synthese_sans_article(config, stockage, fabrique_client):
    client, requetes = fabrique_client([reponse_chat(SYNTHESE)])
    fin = datetime.now(UTC)
    assert generer_synthese(client, config, stockage, fin - timedelta(days=7), fin) is None
    assert requetes == []  # aucun appel inutile


def test_alerte_taux_erreur(config, stockage, fabrique_client):
    _articles(stockage, 4)
    config.production["pause_entre_appels_s"] = 0
    client, _ = fabrique_client([httpx.Response(400, json={}), reponse_chat(ANALYSE_VALIDE)])
    analyser_en_attente(client, config, stockage)
    indicateurs, _ = calculer_indicateurs(config, stockage)
    taux = next(i for i in indicateurs if i.nom == "Taux d'erreur")
    assert taux.valeur == pytest.approx(0.25) and taux.en_alerte
    assert any("Taux d'erreur" in a for a in verifier_alertes(indicateurs))


def test_detection_langue():
    assert est_en_francais("La CNIL publie des recommandations pour les collectivités.")
    assert not est_en_francais("The company released a new model for the market.")


def test_jeu_test_non_annote_refuse(tmp_path):
    chemin = tmp_path / "jeu.json"
    chemin.write_text(json.dumps({"articles": [{"id": "1", "annotation": {"categorie": None, "pertinence": 3}}]}))
    with pytest.raises(ValueError, match="non annoté"):
        charger_jeu_test(chemin)


def test_benchmark_calcule_les_metriques(config, stockage, fabrique_client, tmp_path):
    config.production["pause_entre_appels_s"] = 0
    articles = [
        {"id": "a", "source_id": "cnil", "titre": "T1", "contenu": "c",
         "annotation": {"categorie": "reglementaire", "pertinence": 4}},
        {"id": "b", "source_id": "next", "titre": "T2", "contenu": "c",
         "annotation": {"categorie": "technique", "pertinence": 5}},
    ]
    client, _ = fabrique_client([reponse_chat(ANALYSE_VALIDE)])
    res = evaluer_service(client.fournisseur, config, articles, stockage, tmp_path, client=client).resume()
    assert res["F4_json_conforme_pct"] == 100.0
    assert res["F1_exactitude_pct"] == 50.0        # 1 catégorie sur 2
    assert res["F2_ecart_moyen"] == 0.5            # |5-4| et |5-5|
    assert res["F3_resume_fr_pct"] == 100.0
    assert (tmp_path / "mistral.jsonl").exists()


def test_hebdo_lance_le_monitoring_meme_si_la_synthese_echoue(monkeypatch):
    # Cas réel du 06/11/2026 : synthèse coupée (délai dépassé) -> le monitorage doit quand même tourner.
    from veilleia import cli
    from veilleia.ia_client import ErreurServiceIA

    appels = []

    def echec(*_):
        raise ErreurServiceIA("Échec après 3 tentatives : ReadTimeout")

    monkeypatch.setattr(cli, "cmd_collecter", lambda *_: appels.append("collecte") or 0)
    monkeypatch.setattr(cli, "cmd_analyser", lambda *_: appels.append("analyse") or 0)
    monkeypatch.setattr(cli, "cmd_synthetiser", echec)
    monkeypatch.setattr(cli, "cmd_monitoring", lambda *_: appels.append("monitoring") or 2)
    assert cli.cmd_hebdo(None, None, None) == 2
    assert appels == ["collecte", "analyse", "monitoring"]

def test_synthese_coupee_signalee_et_alerte(config, stockage, fabrique_client):
    # Cas réel du 06/11/2026 : JSON coupé par le plafond de tokens -> message explicite + alerte au monitorage.
    from veilleia.ia_client import ErreurServiceIA

    _articles(stockage)
    config.production["pause_entre_appels_s"] = 0
    client, _ = fabrique_client([reponse_chat(ANALYSE_VALIDE)])
    analyser_en_attente(client, config, stockage)
    coupee = reponse_chat('{"chapeau": "Semaine marquée par', tokens=(3000, 8000))
    coupee["choices"][0]["finish_reason"] = "length"
    client, _ = fabrique_client([coupee])
    debut, fin = datetime.now(UTC) - timedelta(days=7), datetime.now(UTC)
    with pytest.raises(ErreurServiceIA, match="max_tokens_synthese"):
        generer_synthese(client, config, stockage, debut, fin)
    indicateurs, _ = calculer_indicateurs(config, stockage)
    assert next(i for i in indicateurs if i.nom == "Dernière synthèse en échec").en_alerte

def test_benchmark_n_impute_pas_les_refus_de_quota_au_modele(config, stockage, fabrique_client, tmp_path):
    # Cas réel du 06/11/2026 : 7 refus HTTP 429 de Gemini comptés à tort comme « JSON non conforme ».
    config.production["pause_entre_appels_s"] = 0
    articles = [{"id": x, "source_id": "cnil", "titre": x, "contenu": "c",
                 "annotation": {"categorie": "reglementaire", "pertinence": 5}} for x in "abc"]
    refus = httpx.Response(429, json={"error": "quota"})
    client, _ = fabrique_client([refus, refus, refus, reponse_chat("pas du JSON"), reponse_chat(ANALYSE_VALIDE)])
    res = evaluer_service(client.fournisseur, config, articles, stockage, tmp_path, client=client).resume()
    assert res["reponses_recues"] == 2
    assert res["F4_json_conforme_pct"] == 50.0     # 1 conforme sur 2 réponses reçues
    assert res["erreurs_service"] == 1             # le refus de quota est compté à part


def test_limite_de_debit_respectee(config, monkeypatch):
    from veilleia import ia_client

    pauses = []
    monkeypatch.setattr(ia_client.time, "sleep", pauses.append)
    f = config.fournisseur("mistral")
    f.requetes_par_minute = 10                      # 1 appel toutes les 6 s au plus
    client = ia_client.ClientIA(f, client_http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=reponse_chat("OK")))))
    client.completer([{"role": "user", "content": "x"}], "petit", json_attendu=False)
    client.completer([{"role": "user", "content": "x"}], "petit", json_attendu=False)
    assert len(pauses) == 1 and 5.5 < pauses[0] <= 6