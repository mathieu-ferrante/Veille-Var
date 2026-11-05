from datetime import UTC, datetime

import httpx

from veilleia.collecte import Source, collecter, date_francaise, parser_flux, texte_brut

MAINTENANT = datetime(2026, 11, 5, 12, tzinfo=UTC)

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title>
<item><title>AI Act : nouvelles lignes directrices</title><link>https://exemple.fr/a1</link>
<pubDate>Wed, 04 Nov 2026 10:00:00 +0000</pubDate>
<description>&lt;p&gt;La Commission publie des &lt;b&gt;lignes directrices&lt;/b&gt;.&lt;/p&gt;</description></item>
<item><title>Article ancien</title><link>https://exemple.fr/vieux</link>
<pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate><description>vieux</description></item>
<item><title>Date en francais</title><link>https://exemple.fr/fr</link>
<pubDate>Vendredi 30 octobre 2026</pubDate><description>texte</description></item>
<item><title></title><link>https://exemple.fr/sans-titre</link></item>
</channel></rss>"""

SOURCE = Source(id="test", nom="Test", url="https://exemple.fr/rss", theme="reglementaire")


def test_texte_brut_retire_html():
    assert texte_brut("<p>Bonjour&nbsp;<b>le</b>   monde</p>") == "Bonjour le monde"


def test_date_francaise():
    assert date_francaise("Vendredi 30 octobre 2026") == datetime(2026, 10, 30, tzinfo=UTC)
    assert date_francaise("pas de date") is None


def test_parser_flux_filtre_anciens_et_sans_titre():
    articles, nb = parser_flux(SOURCE, RSS, jours_max=8, max_par_source=10, taille_max=100, maintenant=MAINTENANT)
    assert nb == 4
    assert [a.url for a in articles] == ["https://exemple.fr/a1", "https://exemple.fr/fr"]
    assert articles[0].contenu == "La Commission publie des lignes directrices ."
    assert articles[1].date_pub.startswith("2026-10-30")


def test_parser_flux_respecte_plafond():
    articles, _ = parser_flux(SOURCE, RSS, jours_max=8, max_par_source=1, taille_max=100, maintenant=MAINTENANT)
    assert len(articles) == 1


def test_collecte_dedoublonne_et_continue_si_source_en_erreur(stockage, monkeypatch):
    monkeypatch.setattr("veilleia.collecte.parser_flux.__defaults__", (MAINTENANT,))

    def gestionnaire(req: httpx.Request) -> httpx.Response:
        return httpx.Response(503) if "panne" in str(req.url) else httpx.Response(200, content=RSS)

    client = httpx.Client(transport=httpx.MockTransport(gestionnaire))
    sources = [SOURCE, Source(id="panne", nom="Panne", url="https://panne.fr/rss", theme="technique")]
    conf = {"jours_max": 8, "max_par_source": 10, "taille_max_contenu": 500}

    bilan1 = collecter(sources, stockage, conf, client)
    bilan2 = collecter(sources, stockage, conf, client)

    assert bilan1 == {"sources_ok": 1, "sources_erreur": 1, "nouveaux": 2}
    assert bilan2["nouveaux"] == 0  # déjà connus : pas de nouvel appel au modèle
    etats = {c["source_id"]: c["statut"] for c in stockage.derniere_collecte_par_source()}
    assert etats == {"panne": "erreur", "test": "ok"}
