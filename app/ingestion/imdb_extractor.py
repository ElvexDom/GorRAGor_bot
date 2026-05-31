import sqlite3
import gzip
import os
import urllib.request
import logging
from typing import List, Optional

from app.models import TMDBMovie, IMDBData

logger = logging.getLogger(__name__)

IMDB_DB_PATH  = "data/tmp/imdb.db"
IMDB_TMP_DIR  = "data/tmp/imdb_tsv"
IMDB_BASE_URL = "https://datasets.imdbws.com"
MIN_VOTES     = 1000

IMDB_FILES = [
    "title.basics.tsv.gz",
    "title.ratings.tsv.gz",
    "title.principals.tsv.gz",
    "name.basics.tsv.gz",
]


class IMDBExtractor:
    def __init__(self, db_path: str = IMDB_DB_PATH):
        self.db_path = db_path
        self.conn = None
        self.horror_tconsts = set()

        if not os.path.exists(self.db_path):
            logger.info("Base IMDB absente — construction depuis les datasets officiels IMDB...")
            self._build()

        if not os.path.exists(self.db_path):
            logger.error("Base IMDB introuvable apres construction : %s", self.db_path)
            return

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = OFF")
        self.conn.execute("PRAGMA synchronous = OFF")
        self.conn.execute("PRAGMA cache_size = -2000")

        self._load_horror_tconsts()
        self._load_titles_by_year()
        logger.info("IMDB pret : %d films Horror eligibles (votes >= %d).",
                    len(self.horror_tconsts), MIN_VOTES)

    # ------------------------------------------------------------------
    # Construction de la base IMDB
    # ------------------------------------------------------------------

    def _download_tsv(self, filename: str) -> str:
        """Télécharge un fichier TSV IMDB si absent du cache."""
        os.makedirs(IMDB_TMP_DIR, exist_ok=True)
        dest = os.path.join(IMDB_TMP_DIR, filename)
        if os.path.exists(dest):
            logger.info("Cache TSV : %s (skip)", filename)
            return dest
        url = f"{IMDB_BASE_URL}/{filename}"
        logger.info("Telechargement : %s ...", url)
        urllib.request.urlretrieve(url, dest)
        return dest

    def _stream_tsv(self, filepath: str):
        """Lit un fichier .tsv.gz ligne par ligne."""
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")
            for line in f:
                yield dict(zip(header, line.strip().split("\t")))

    def _build(self):
        """
        Télécharge les datasets officiels IMDB et construit imdb.db.
        Filtre : films Horror + numVotes >= 1000.
        """
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

        # --- title_basics : films Horror ---
        logger.info("[1/4] title_basics : import films Horror...")
        conn.execute("""CREATE TABLE IF NOT EXISTS title_basics (
            tconst TEXT PRIMARY KEY, titleType TEXT, primaryTitle TEXT,
            originalTitle TEXT, startYear TEXT, genres TEXT)""")

        horror_tconsts = set()
        batch = []
        for row in self._stream_tsv(self._download_tsv("title.basics.tsv.gz")):
            if row.get("titleType") != "movie":
                continue
            if "Horror" not in row.get("genres", ""):
                continue
            horror_tconsts.add(row["tconst"])
            batch.append((row["tconst"], row["titleType"], row["primaryTitle"],
                          row["originalTitle"], row.get("startYear"), row.get("genres")))
            if len(batch) >= 5000:
                conn.executemany("INSERT OR IGNORE INTO title_basics VALUES (?,?,?,?,?,?)", batch)
                batch = []
        if batch:
            conn.executemany("INSERT OR IGNORE INTO title_basics VALUES (?,?,?,?,?,?)", batch)
        conn.commit()
        logger.info("title_basics : %d films Horror.", len(horror_tconsts))

        # --- title_ratings : Horror + numVotes >= 1000 ---
        logger.info("[2/4] title_ratings : import notes (votes >= %d)...", MIN_VOTES)
        conn.execute("""CREATE TABLE IF NOT EXISTS title_ratings (
            tconst TEXT PRIMARY KEY, averageRating REAL, numVotes INTEGER)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_r_tconst ON title_ratings(tconst)")

        qualified = set()
        batch = []
        for row in self._stream_tsv(self._download_tsv("title.ratings.tsv.gz")):
            if row["tconst"] not in horror_tconsts:
                continue
            try:
                votes = int(row.get("numVotes", 0))
            except ValueError:
                continue
            if votes < MIN_VOTES:
                continue
            qualified.add(row["tconst"])
            batch.append((row["tconst"], float(row["averageRating"]), votes))
            if len(batch) >= 5000:
                conn.executemany("INSERT OR IGNORE INTO title_ratings VALUES (?,?,?)", batch)
                batch = []
        if batch:
            conn.executemany("INSERT OR IGNORE INTO title_ratings VALUES (?,?,?)", batch)
        conn.commit()
        logger.info("title_ratings : %d films qualifies.", len(qualified))

        # --- title_principals : casting des films qualifiés ---
        logger.info("[3/4] title_principals : import casting...")
        conn.execute("""CREATE TABLE IF NOT EXISTS title_principals (
            tconst TEXT, ordering INTEGER, nconst TEXT, category TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_p_tconst ON title_principals(tconst)")

        target_cats = {"actor", "actress", "director", "self"}
        nconsts = set()
        batch = []
        for row in self._stream_tsv(self._download_tsv("title.principals.tsv.gz")):
            if row["tconst"] not in qualified:
                continue
            if row.get("category") not in target_cats:
                continue
            nconsts.add(row["nconst"])
            batch.append((row["tconst"], row.get("ordering"), row["nconst"], row.get("category")))
            if len(batch) >= 5000:
                conn.executemany("INSERT OR IGNORE INTO title_principals VALUES (?,?,?,?)", batch)
                batch = []
        if batch:
            conn.executemany("INSERT OR IGNORE INTO title_principals VALUES (?,?,?,?)", batch)
        conn.commit()
        logger.info("title_principals : %d entrees.", len(batch))

        # --- name_basics : noms des personnes ---
        logger.info("[4/4] name_basics : import noms...")
        conn.execute("""CREATE TABLE IF NOT EXISTS name_basics (
            nconst TEXT PRIMARY KEY, primaryName TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_n_nconst ON name_basics(nconst)")

        batch = []
        for row in self._stream_tsv(self._download_tsv("name.basics.tsv.gz")):
            if row["nconst"] not in nconsts:
                continue
            batch.append((row["nconst"], row.get("primaryName")))
            if len(batch) >= 5000:
                conn.executemany("INSERT OR IGNORE INTO name_basics VALUES (?,?)", batch)
                batch = []
        if batch:
            conn.executemany("INSERT OR IGNORE INTO name_basics VALUES (?,?)", batch)
        conn.commit()
        conn.close()
        logger.info("Base IMDB construite : %s", self.db_path)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _load_horror_tconsts(self):
        """Jointure title_basics ↔ title_ratings filtrée Horror + votes >= 1000."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.tconst FROM title_basics b
            JOIN title_ratings r ON b.tconst = r.tconst
            WHERE b.titleType = 'movie'
              AND b.genres LIKE '%Horror%'
              AND r.numVotes >= ?
        """, (MIN_VOTES,))
        self.horror_tconsts = {row["tconst"] for row in cursor.fetchall()}

    def _load_titles_by_year(self):
        """
        Charge un index {année: [(tconst, titre)]} pour le fuzzy matching.
        Pré-filtre sur Horror + votes >= 1000 pour limiter les comparaisons.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.tconst, b.primaryTitle, b.startYear
            FROM title_basics b
            JOIN title_ratings r ON b.tconst = r.tconst
            WHERE b.titleType = 'movie'
              AND b.genres LIKE '%Horror%'
              AND r.numVotes >= ?
        """, (MIN_VOTES,))
        self.titles_by_year = {}
        for row in cursor.fetchall():
            year = row["startYear"]
            self.titles_by_year.setdefault(year, []).append(
                (row["tconst"], row["primaryTitle"])
            )

    def _fuzzy_match(self, title: str, year: Optional[str], threshold: int = 85) -> Optional[str]:
        """
        Niveau 3 MDM — Fuzzy matching sur [Titre + Année] via distance de Levenshtein.
        Retourne le tconst le plus proche si le score dépasse le seuil.
        """
        from rapidfuzz import process, fuzz
        candidates = self.titles_by_year.get(str(year), []) if year else []
        if not candidates:
            return None
        titles = [c[1] for c in candidates]
        result = process.extractOne(title, titles, scorer=fuzz.ratio, score_cutoff=threshold)
        if result:
            matched_title, score, idx = result
            logger.debug("Fuzzy match : '%s' → '%s' (%d%%)", title, matched_title, score)
            return candidates[idx][0]
        return None

    def build_imdb_data(self, movies: List[TMDBMovie]) -> List[IMDBData]:
        """Enrichit les films avec casting et ratings IMDB."""
        if not self.conn or not movies:
            return []

        cursor = self.conn.cursor()
        results = []

        for movie in movies:
            try:
                year = movie.release_date.year if movie.release_date else None
                imdb_id = None

                # Niveau 2 MDM : correspondance exacte [Titre + Année]
                sql = """
                    SELECT b.tconst FROM title_basics b
                    JOIN title_ratings r ON b.tconst = r.tconst
                    WHERE b.primaryTitle = ?
                      AND b.titleType = 'movie'
                      AND b.genres LIKE '%Horror%'
                      AND r.numVotes >= ?
                """
                params = [movie.title, MIN_VOTES]
                if year:
                    sql += " AND b.startYear = ?"
                    params.append(str(year))
                cursor.execute(sql, params)
                row = cursor.fetchone()

                if row:
                    imdb_id = row["tconst"]
                else:
                    # Niveau 3 MDM : fuzzy matching [Titre + Année]
                    imdb_id = self._fuzzy_match(movie.title, str(year) if year else None)

                if not imdb_id:
                    continue

                cursor.execute(
                    "SELECT averageRating, numVotes FROM title_ratings WHERE tconst = ?",
                    (imdb_id,)
                )
                rating_row = cursor.fetchone()
                if not rating_row:
                    continue

                results.append(IMDBData(
                    tmdb_id     = movie.tmdb_id,
                    imdb_id     = imdb_id,
                    imdb_rating = float(rating_row["averageRating"]),
                    num_votes   = int(rating_row["numVotes"]),
                    director    = self._get_principals(cursor, imdb_id, ("director",)),
                    actors      = self._get_principals(cursor, imdb_id, ("actor", "actress", "self")),
                ))

                if len(results) % 1000 == 0:
                    logger.info("IMDB : %d films enrichis...", len(results))

            except Exception:
                continue

        logger.info("IMDB : %d films mis a jour.", len(results))
        return results

    def _get_principals(self, cursor, tconst: str, categories: tuple) -> Optional[str]:
        placeholders = ",".join("?" for _ in categories)
        query = f"""
            SELECT n.primaryName FROM title_principals p
            JOIN name_basics n ON p.nconst = n.nconst
            WHERE p.tconst = ? AND p.category IN ({placeholders})
            ORDER BY p.ordering ASC LIMIT 5
        """
        try:
            cursor.execute(query, [tconst] + list(categories))
            names = [row["primaryName"] for row in cursor.fetchall()]
            return ", ".join(names) if names else None
        except sqlite3.Error:
            return None

    def close(self):
        if self.conn:
            self.conn.close()
