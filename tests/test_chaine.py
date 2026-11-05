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
