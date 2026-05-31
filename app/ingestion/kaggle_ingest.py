import polars as pl
import os
import logging
from typing import List

from app.models import TMDBMovie, KaggleData
from app.utils.normalizers import clean_txt, normalize_date

logger = logging.getLogger(__name__)

KAGGLE_DATASET  = "evangower/horror-movies"
KAGGLE_FILENAME = "horror_movies.csv"
PARTS_DIR       = "data/tmp/kaggle_parts"
PART_SIZE       = 10_000


class KaggleIngestor:
    def __init__(self, csv_path: str = "data/tmp/kaggle.csv"):
        self.csv_path = csv_path

    def _download(self):
        """Télécharge le dataset Kaggle si absent."""
        try:
            import kaggle
            import glob
            kaggle.api.authenticate()
            dest_dir = os.path.dirname(self.csv_path)
            os.makedirs(dest_dir, exist_ok=True)
            kaggle.api.dataset_download_files(
                KAGGLE_DATASET, path=dest_dir, unzip=True, quiet=False,
            )
            # Renomme le fichier extrait sous son nom d'origine
            for f in glob.glob(os.path.join(dest_dir, "*.csv")):
                if f != self.csv_path:
                    os.rename(f, self.csv_path)
                    logger.info("Fichier renomme : %s -> %s", f, self.csv_path)
                    break
            logger.info("Dataset Kaggle telecharge : %s", self.csv_path)
        except Exception as e:
            logger.error("Impossible de telecharger le dataset Kaggle : %s", e)

    def _load(self) -> pl.DataFrame | None:
        """Charge le CSV en DataFrame Polars. Télécharge si absent."""
        if not os.path.exists(self.csv_path):
            logger.info("Fichier Kaggle absent — telechargement en cours...")
            self._download()

        if not os.path.exists(self.csv_path):
            logger.error("Fichier Kaggle introuvable : %s", self.csv_path)
            return None

        try:
            df = pl.read_csv(self.csv_path, infer_schema_length=10000)
            logger.info("CSV Kaggle charge : %d lignes.", len(df))
            return df
        except Exception as e:
            logger.error("Erreur lecture CSV : %s", e)
            return None

    def split_for_spark(self) -> str:
        """
        Partitionne le CSV en fichiers de ~10 000 lignes pour PySpark.
        Retourne le chemin du dossier contenant les partitions.
        """
        df = self._load()
        if df is None:
            return PARTS_DIR

        os.makedirs(PARTS_DIR, exist_ok=True)

        # Colonnes utiles pour Spark
        cols = [c for c in ["id", "overview", "title", "release_date"] if c in df.columns]
        df_spark = df.select(cols)

        total = len(df_spark)
        n_parts = (total // PART_SIZE) + (1 if total % PART_SIZE else 0)

        for i in range(n_parts):
            part = df_spark.slice(i * PART_SIZE, PART_SIZE)
            part_path = os.path.join(PARTS_DIR, f"part_{i+1:03d}.csv")
            part.write_csv(part_path)

        logger.info("Kaggle splitte en %d fichiers dans %s.", n_parts, PARTS_DIR)
        return PARTS_DIR

    def build_kaggle_data(self, movies: List[TMDBMovie]) -> List[KaggleData]:
        """
        Construit les objets KaggleData à partir du CSV.
        Dédoublonne sur title + release_date avant fusion.
        """
        if not movies:
            return []

        df = self._load()
        if df is None:
            return []

        id_col = "id" if "id" in df.columns else df.columns[1]
        cols_to_keep = [id_col, "overview", "budget", "revenue", "runtime", "tagline", "genre_names"]
        available_cols = [c for c in cols_to_keep if c in df.columns]

        if "release_date" in df.columns:
            df = df.with_columns(
                pl.col("release_date").map_elements(
                    lambda x: str(normalize_date(x)) if x and normalize_date(x) else None,
                    return_dtype=pl.String
                )
            )

        dedup_cols = [c for c in ["title", "release_date"] if c in df.columns]
        df_dedup = df.unique(subset=dedup_cols) if dedup_cols else df

        kaggle_dict = {}
        for row in df_dedup.select(available_cols).to_dicts():
            try:
                raw_id = row.get(id_col)
                if raw_id is not None:
                    kaggle_dict[int(float(str(raw_id)))] = row
            except Exception:
                continue

        results = []
        for movie in movies:
            data = kaggle_dict.get(movie.tmdb_id)
            if not data:
                continue

            g = data.get("genre_names", "") or ""
            t = data.get("tagline", "") or ""
            r = data.get("runtime", "") or ""
            details_parts = []
            if g: details_parts.append(f"Genres: {g}")
            if t: details_parts.append(f"Tagline: {t}")
            if r: details_parts.append(f"Duree: {r} min")

            results.append(KaggleData(
                tmdb_id          = movie.tmdb_id,
                synopsis         = clean_txt(data.get("overview")),
                literary_details = clean_txt(" | ".join(details_parts)) if details_parts else None,
                budget           = data.get("budget"),
                revenue          = data.get("revenue"),
            ))

        logger.info("Kaggle : %d/%d films enrichis.", len(results), len(movies))
        return results
