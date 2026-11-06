"""Tests des corrections issues de la relecture du code (sécurité, robustesse, exactitude des mesures)."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from veilleia import cli, diffusion, ia_client
from veilleia.collecte import Source, parser_flux, url_web
from veilleia.ia_client import ErreurServiceIA
from veilleia.prompts import neutraliser
from veilleia.schemas import AnalyseArticle, SyntheseHebdo
from veilleia.stockage import MAX_ECHECS_ANALYSE, Article
from veilleia.synthese import ResultatSynthese, _lien_md, generer_synthese, rendre_html, rendre_markdown

from .conftest import ANALYSE_VALIDE, reponse_chat

MAINTENANT = datetime(2026, 11, 6, 12, tzinfo=UTC)


# --- 1. Diffusion par mail ------------------------------------------------------------------------
class FauxSMTP:
    instances: list[FauxSMTP] = []

    def __init__(self, hote, port, timeout=30, context=None):
        self.hote, self.port, self.context, self.contexte_tls = hote, port, context, None
        FauxSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, context=None):
        self.contexte_tls = context

    def login(self, *_):
        pass

    def send_message(self, _msg):
        pass


@pytest.fixture
def smtp(monkeypatch, tmp_path):
    FauxSMTP.instances = []
    monkeypatch.setattr(diffusion.smtplib, "SMTP", FauxSMTP)
    monkeypatch.setattr(diffusion.smtplib, "SMTP_SSL", FauxSMTP)
    for k, v in {"SMTP_HOST": "smtp.exemple.fr", "SMTP_FROM": "veille@exemple.fr", "SMTP_TO": "dsi@exemple.fr",
                 "SMTP_PORT": "587"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    (tmp_path / "s.html").write_text("<p>x</p>", encoding="utf-8")
    (tmp_path / "s.md").write_text("x", encoding="utf-8")
    return tmp_path / "s.html", tmp_path / "s.md"


def test_smtp_certificat_verifie(smtp):
    assert diffusion.envoyer_synthese(*smtp, "objet")
    contexte = FauxSMTP.instances[0].contexte_tls
    assert contexte is not None and contexte.check_hostname  # certificat et nom de serveur contrôlés


def test_smtp_port_465_et_erreurs_sans_plantage(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "465")
    assert diffusion.envoyer_synthese(*smtp, "objet")
    assert FauxSMTP.instances[0].context is not None and FauxSMTP.instances[0].contexte_tls is None

    def panne(*_a, **_k):
        raise smtplib.SMTPConnectError(421, "indisponible")

    monkeypatch.setattr(diffusion.smtplib, "SMTP_SSL", panne)
    assert diffusion.envoyer_synthese(*smtp, "objet") is False  # erreur journalisée, pas d'exception
    monkeypatch.setenv("SMTP_USER", "veille")  # utilisateur sans mot de passe
    assert diffusion.envoyer_synthese(*smtp, "objet") is False


# --- 2. Liens des flux RSS -------------------------------------------------------------------------
def test_liens_non_web_ecartes_et_markdown_echappe():
    assert url_web("https://www.cnil.fr/a") and not url_web("javascript:alert(1)") and not url_web("data:x")
    flux = (b"<rss><channel><item><title>Piege</title><link>javascript:alert(1)</link></item>"
            b"<item><title>Normal</title><link>https://exemple.fr/a</link></item></channel></rss>")
    src = Source(id="s", nom="S", url="https://exemple.fr/rss", theme="technique", langue="fr", fiabilite=3)
    articles, _ = parser_flux(src, flux, 8, 30, 2500, maintenant=MAINTENANT)
    assert [a.titre for a in articles] == ["Normal"]
    assert _lien_md("Titre [x]", "https://ex.fr/a_(b)") == "[Titre \\[x\\]](https://ex.fr/a_%28b%29)"


# --- 3. Chaîne hebdomadaire ------------------------------------------------------------------------
def test_hebdo_continue_sur_erreur_imprevue(monkeypatch):
    appels = []

    def collecte_en_panne(*_):
        raise OSError("disque plein")

    monkeypatch.setattr(cli, "cmd_collecter", collecte_en_panne)
    monkeypatch.setattr(cli, "cmd_analyser", lambda *_: appels.append("analyse") or 0)
    monkeypatch.setattr(cli, "cmd_synthetiser", lambda *_: appels.append("synthese") or 0)
    monkeypatch.setattr(cli, "cmd_monitoring", lambda *_: appels.append("monitoring") or 0)
    assert cli.cmd_hebdo(None, None, None) == 1
    assert appels == ["analyse", "synthese", "monitoring"]


# --- 4. Date de fin --------------------------------------------------------------------------------
def test_date_de_fin_inclut_la_journee():
    assert cli.date_de_fin("2026-11-06") == datetime(2026, 11, 6, 23, 59, 59, tzinfo=UTC)
    assert cli.date_de_fin("2026-11-06T10:00+01:00").utcoffset() == timedelta(hours=1)
    assert cli.date_de_fin(None) is None
    with pytest.raises(Exception, match="invalide"):
        cli.date_de_fin("06/11/2026")


# --- 5. Points sans source valide ------------------------------------------------------------------
def _articles(stockage, n=2):
    stockage.inserer_articles([Article(source_id="cnil", titre=f"P{i}", url=f"https://ex.fr/{i}",
                                       date_pub=(datetime.now(UTC) - timedelta(days=1)).isoformat(), contenu="c")
                               for i in range(n)])
    for row in stockage.articles_a_analyser():
        stockage.enregistrer_analyse(row["id"], ANALYSE_VALIDE, "test")


def test_point_sans_source_valide_retire(config, stockage, fabrique_client):
    _articles(stockage)
    synthese = {"chapeau": "Semaine marquée par des recommandations de la CNIL.", "a_retenir": [],
                "sections": [{"theme": "Réglementation", "points": [
                    {"titre": "Sourcé", "texte": "Point appuyé sur une publication.", "references": [1, 1]}]},
                    {"theme": "Technique", "points": [
                        {"titre": "Inventé", "texte": "Point qui cite un article inexistant.", "references": [99]}]}]}
    client, _ = fabrique_client([reponse_chat(synthese)])
    r = generer_synthese(client, config, stockage, datetime.now(UTC) - timedelta(days=7), datetime.now(UTC))
    assert [s.theme for s in r.synthese.sections] == ["Réglementation"]
    assert r.synthese.sections[0].points[0].references == [1]  # doublon retiré
    html_ = rendre_html(r, "Agent")
    assert "Inventé" not in html_ and '<ul class="sources-point"></ul>' not in html_
    assert "Inventé" not in rendre_markdown(r, "Agent")


def test_rendu_sans_reference_ne_cree_pas_de_liste_vide():
    s = SyntheseHebdo.model_validate({"chapeau": "Chapeau suffisamment long pour le schéma.", "sections": [
        {"theme": "Technique", "points": [{"titre": "Titre", "texte": "Texte du point.", "references": [1]}]}]})
    s.sections[0].points[0].references = []
    r = ResultatSynthese(s, [], MAINTENANT, MAINTENANT, "F", "m")
    assert "<ul class=\"sources-point\">" not in rendre_html(r, "Agent")


# --- 6 et 11. Latence et nombre d'essais journalisés ------------------------------------------------
def test_latence_exclut_les_pauses_entre_tentatives(fabrique_client, stockage, monkeypatch):
    horloge = [0.0]
    monkeypatch.setattr(ia_client.time, "perf_counter", lambda: horloge[0])
    monkeypatch.setattr(ia_client.time, "sleep", lambda s: horloge.__setitem__(0, horloge[0] + s))
    client, _ = fabrique_client([httpx.Response(429, headers={"retry-after": "20"}, json={}),
                                 reponse_chat(ANALYSE_VALIDE)])
    rep = client.completer([{"role": "user", "content": "x"}], "petit")
    assert rep.tentatives == 2 and rep.latence_s < 1  # les 20 s d'attente ne sont pas de la latence


def test_nombre_reel_de_tentatives_journalise(fabrique_client, stockage):
    client, requetes = fabrique_client([httpx.Response(401, json={"error": "cle"})])
    with pytest.raises(ErreurServiceIA):
        client.completer_json([{"role": "user", "content": "x"}], AnalyseArticle, "petit")
    assert len(requetes) == 1
    assert stockage.cnx.execute("SELECT tentatives FROM appels_ia").fetchone()[0] == 1


# --- 7, 8, 10. Stockage ----------------------------------------------------------------------------
def test_sources_retirees_ignorees_par_le_monitorage(stockage):
    stockage.journaliser_collecte("active", "ok")
    stockage.journaliser_collecte("retiree", "erreur", erreur="HTTP 404")
    assert {r["source_id"] for r in stockage.derniere_collecte_par_source(["active"])} == {"active"}


def test_analyse_en_echec_abandonnee_apres_plusieurs_essais(stockage):
    stockage.inserer_articles([Article(source_id="s", titre="T", url="https://ex.fr/1", date_pub=None, contenu="")])
    (row,) = stockage.articles_a_analyser()
    for _ in range(MAX_ECHECS_ANALYSE):
        stockage.enregistrer_erreur_analyse(row["id"], "JSON coupé")
    assert stockage.articles_a_analyser() == []


def test_limite_zero_respectee(stockage):
    stockage.inserer_articles([Article(source_id="s", titre="T", url="https://ex.fr/1", date_pub=None, contenu="")])
    assert stockage.articles_a_analyser(limite=0) == []
    assert len(stockage.articles_a_analyser(limite=None)) == 1


# --- 9. Injection de prompt ------------------------------------------------------------------------
@pytest.mark.parametrize("balise", ["</Publication>", "</publication >", "< /PUBLICATION>", "<publications>"])
def test_neutralisation_insensible_a_la_casse(balise):
    resultat = neutraliser(f"avant {balise} après")
    assert "</publication>" not in resultat and "<publication>" not in resultat
    assert "<publications>" not in resultat
