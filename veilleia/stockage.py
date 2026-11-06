"""Stockage SQLite : articles collectés, analyses, appels au service d'IA, collectes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            TEXT PRIMARY KEY,          -- empreinte SHA-256 de l'URL normalisée
    source_id     TEXT NOT NULL,
    titre         TEXT NOT NULL,
    url           TEXT NOT NULL,
    date_pub      TEXT,                      -- ISO 8601 UTC
    contenu       TEXT,                      -- texte brut tronqué
    langue        TEXT,
    collecte_le   TEXT NOT NULL,
    -- résultats de l'analyse par le service d'IA
    categorie     TEXT,
    pertinence    INTEGER,
    resume        TEXT,
    mots_cles     TEXT,                      -- JSON
    entites       TEXT,                      -- JSON
    analyse_le    TEXT,
    analyse_par   TEXT,                      -- fournisseur/modèle
    erreur_analyse TEXT,
    nb_echecs     INTEGER NOT NULL DEFAULT 0 -- analyses en échec (abandon après MAX_ECHECS_ANALYSE)
);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date_pub);

-- Journal de chaque appel au service d'IA (monitorage)
CREATE TABLE IF NOT EXISTS appels_ia (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    horodatage    TEXT NOT NULL,
    fournisseur   TEXT NOT NULL,
    modele        TEXT NOT NULL,
    tache         TEXT NOT NULL,             -- analyse / synthese / benchmark / test
    statut        TEXT NOT NULL,             -- ok / erreur
    code_http     INTEGER,
    latence_s     REAL,
    tokens_entree INTEGER,
    tokens_sortie INTEGER,
    cout_eur      REAL,
    json_valide   INTEGER,                   -- 1 / 0 / NULL (non applicable)
    tentatives    INTEGER,
    erreur        TEXT
);
CREATE INDEX IF NOT EXISTS idx_appels_date ON appels_ia(horodatage);

-- Journal des collectes RSS (disponibilité des sources)
CREATE TABLE IF NOT EXISTS collectes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    horodatage    TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    statut        TEXT NOT NULL,             -- ok / erreur
    nb_entrees    INTEGER,
    nb_nouveaux   INTEGER,
    erreur        TEXT
);

-- Historique des synthèses produites
CREATE TABLE IF NOT EXISTS syntheses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    horodatage    TEXT NOT NULL,
    debut         TEXT NOT NULL,
    fin           TEXT NOT NULL,
    nb_articles   INTEGER,
    fichier_html  TEXT,
    fichier_md    TEXT
);
"""


MAX_ECHECS_ANALYSE = 3  # au-delà, la publication n'est plus renvoyée au service (pas de refacturation sans fin)


def maintenant() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def empreinte_url(url: str) -> str:
    normalisee = url.strip().split("#")[0].rstrip("/").lower()
    return hashlib.sha256(normalisee.encode("utf-8")).hexdigest()[:32]


@dataclass
class Article:
    source_id: str
    titre: str
    url: str
    date_pub: str | None
    contenu: str
    langue: str | None = None
    id: str = ""
    categorie: str | None = None
    pertinence: int | None = None
    resume: str | None = None
    mots_cles: list[str] = field(default_factory=list)
    entites: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = empreinte_url(self.url)


class Stockage:
    def __init__(self, chemin: Path | str) -> None:
        if str(chemin) != ":memory:":
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        self.cnx = sqlite3.connect(str(chemin))
        self.cnx.row_factory = sqlite3.Row
        self.cnx.executescript(SCHEMA)
        self._migrer()

    def _migrer(self) -> None:
        """Ajoute les colonnes apparues après la création d'une base existante."""
        colonnes = {r["name"] for r in self.cnx.execute("PRAGMA table_info(articles)")}
        if "nb_echecs" not in colonnes:
            with self.cnx:
                self.cnx.execute("ALTER TABLE articles ADD COLUMN nb_echecs INTEGER NOT NULL DEFAULT 0")

    def fermer(self) -> None:
        self.cnx.close()

    # --- articles -----------------------------------------------------------
    def inserer_articles(self, articles: Iterable[Article]) -> int:
        """Insère les articles inconnus (dédoublonnage par URL). Renvoie le nombre de nouveaux."""
        nouveaux = 0
        with self.cnx:
            for a in articles:
                cur = self.cnx.execute(
                    "INSERT OR IGNORE INTO articles (id, source_id, titre, url, date_pub, contenu, langue,"
                    " collecte_le) VALUES (?,?,?,?,?,?,?,?)",
                    (a.id, a.source_id, a.titre, a.url, a.date_pub, a.contenu, a.langue, maintenant()),
                )
                nouveaux += cur.rowcount
        return nouveaux

    def articles_a_analyser(self, limite: int | None = None) -> list[sqlite3.Row]:
        """Publications pas encore analysées, hors celles qui ont déjà échoué MAX_ECHECS_ANALYSE fois."""
        sql = "SELECT * FROM articles WHERE analyse_le IS NULL AND nb_echecs < ? ORDER BY date_pub DESC"
        params: tuple[int, ...] = (MAX_ECHECS_ANALYSE,)
        if limite is not None:  # --limite 0 signifie bien « aucune »
            sql += " LIMIT ?"
            params += (max(0, int(limite)),)
        return list(self.cnx.execute(sql, params))

    def enregistrer_analyse(self, article_id: str, analyse: dict[str, Any], analyse_par: str) -> None:
        with self.cnx:
            self.cnx.execute(
                "UPDATE articles SET categorie=?, pertinence=?, resume=?, mots_cles=?, entites=?,"
                " analyse_le=?, analyse_par=?, erreur_analyse=NULL WHERE id=?",
                (
                    analyse["categorie"],
                    analyse["pertinence"],
                    analyse["resume"],
                    json.dumps(analyse.get("mots_cles", []), ensure_ascii=False),
                    json.dumps(analyse.get("entites", []), ensure_ascii=False),
                    maintenant(),
                    analyse_par,
                    article_id,
                ),
            )

    def enregistrer_erreur_analyse(self, article_id: str, erreur: str) -> None:
        with self.cnx:
            self.cnx.execute("UPDATE articles SET erreur_analyse=?, nb_echecs = nb_echecs + 1 WHERE id=?",
                             (erreur[:500], article_id))

    def articles_pour_synthese(self, debut: str, fin: str, pertinence_min: int, limite: int) -> list[sqlite3.Row]:
        return list(
            self.cnx.execute(
                "SELECT * FROM articles WHERE analyse_le IS NOT NULL AND categorie != 'hors_sujet'"
                " AND pertinence >= ? AND COALESCE(date_pub, collecte_le) BETWEEN ? AND ?"
                " ORDER BY pertinence DESC, date_pub DESC LIMIT ?",
                (pertinence_min, debut, fin, limite),
            )
        )

    def compter(self, table: str) -> int:
        if table not in {"articles", "appels_ia", "collectes", "syntheses"}:
            raise ValueError(table)
        return self.cnx.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608

    # --- monitorage ----------------------------------------------------------
    def journaliser_appel(self, **champs: Any) -> None:
        champs.setdefault("horodatage", maintenant())
        colonnes = ", ".join(champs)
        marques = ", ".join("?" for _ in champs)
        with self.cnx:
            self.cnx.execute(f"INSERT INTO appels_ia ({colonnes}) VALUES ({marques})", tuple(champs.values()))  # noqa: S608

    def journaliser_collecte(self, source_id: str, statut: str, nb_entrees: int = 0, nb_nouveaux: int = 0,
                             erreur: str | None = None) -> None:
        with self.cnx:
            self.cnx.execute(
                "INSERT INTO collectes (horodatage, source_id, statut, nb_entrees, nb_nouveaux, erreur)"
                " VALUES (?,?,?,?,?,?)",
                (maintenant(), source_id, statut, nb_entrees, nb_nouveaux, erreur),
            )

    def journaliser_synthese(self, debut: str, fin: str, nb: int, html: str, md: str) -> None:
        with self.cnx:
            self.cnx.execute(
                "INSERT INTO syntheses (horodatage, debut, fin, nb_articles, fichier_html, fichier_md)"
                " VALUES (?,?,?,?,?,?)",
                (maintenant(), debut, fin, nb, html, md),
            )

    def appels_depuis(self, jours: int) -> list[sqlite3.Row]:
        depuis = (datetime.now(UTC) - timedelta(days=jours)).isoformat(timespec="seconds")
        return list(self.cnx.execute("SELECT * FROM appels_ia WHERE horodatage >= ? ORDER BY horodatage", (depuis,)))

    def derniere_collecte_par_source(self, sources_actives: Iterable[str] | None = None) -> list[sqlite3.Row]:
        """Dernière collecte de chaque source. Avec `sources_actives`, les sources retirées de sources.yaml
        sont ignorées (sinon une source supprimée resterait « en erreur » indéfiniment)."""
        lignes = self.cnx.execute(
            "SELECT c.* FROM collectes c JOIN (SELECT source_id, MAX(id) mid FROM collectes"
            " GROUP BY source_id) d ON c.id = d.mid ORDER BY c.source_id"
        )
        if sources_actives is None:
            return list(lignes)
        actives = set(sources_actives)
        return [r for r in lignes if r["source_id"] in actives]
