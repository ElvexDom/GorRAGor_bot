import logging
import os
from typing import List
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, regexp_replace, split, array_distinct, slice, concat_ws, expr

from app.models import TMDBMovie, KaggleData, SparkAnalysis

logger = logging.getLogger(__name__)

PARTS_DIR = "data/tmp/kaggle_parts"


class SparkProcessor:
    def __init__(self, app_name: str = "HorRAGorSparkProcessor"):
        self.spark = SparkSession.builder \
            .appName(app_name) \
            .master("local[*]") \
            .config("spark.driver.memory", "4g") \
            .getOrCreate()
        self.spark.sparkContext.setLogLevel("ERROR")
        logger.info("SparkProcessor : moteur analytique pret.")

    def process(self, movies: List[TMDBMovie], kaggle_data: List[KaggleData]) -> List[SparkAnalysis]:
        """
        Analyse textuelle des synopsis via Spark.
        Lit les fichiers Kaggle splittés depuis PARTS_DIR.
        Priorise le synopsis Kaggle (plus riche) sur l'overview TMDB.
        """
        if not movies:
            return []

        # Fallback en mémoire si les fichiers splittés sont absents
        if os.path.exists(PARTS_DIR) and os.listdir(PARTS_DIR):
            keyword_map = self._process_from_parts()
        else:
            logger.warning("Fichiers Kaggle splittés absents — traitement depuis la mémoire.")
            keyword_map = self._process_from_memory(movies, kaggle_data)

        results = []
        for m in movies:
            kw = keyword_map.get(m.tmdb_id)
            if kw:
                results.append(SparkAnalysis(
                    tmdb_id            = m.tmdb_id,
                    extracted_keywords = kw,
                ))

        logger.info("Spark : %d films analyses.", len(results))
        return results

    def _process_from_parts(self) -> dict:
        """
        Lit les fichiers CSV partitionnés avec Spark et extrait les mots-clés.
        C'est l'usage natif de Spark : traitement distribué de fichiers splittés.
        """
        logger.info("Spark : lecture de %s/*.csv ...", PARTS_DIR)

        df = self.spark.read \
            .option("header", "true") \
            .option("inferSchema", "true") \
            .csv(f"{PARTS_DIR}/*.csv")

        id_col = "id" if "id" in df.columns else df.columns[0]

        processed_df = (
            df.withColumn("words",
                split(lower(regexp_replace(col("overview"), "[^a-zA-Z\\s]", "")), "\\s+"))
            .withColumn("filtered",
                expr("filter(words, x -> length(x) > 3)"))
            .withColumn("keywords",
                concat_ws(", ", slice(array_distinct(col("filtered")), 1, 5)))
            .select(col(id_col).cast("integer").alias("tmdb_id"), "keywords")
            .filter(col("keywords") != "")
        )

        return {row["tmdb_id"]: row["keywords"] for row in processed_df.collect()}

    def _process_from_memory(self, movies: List[TMDBMovie], kaggle_data: List[KaggleData]) -> dict:
        """Fallback : traitement depuis les objets en mémoire."""
        kaggle_map = {k.tmdb_id: k.synopsis for k in kaggle_data if k.synopsis}
        data = [(m.tmdb_id, kaggle_map.get(m.tmdb_id) or m.overview or "") for m in movies]

        df = self.spark.createDataFrame(data, ["tmdb_id", "text"])
        processed_df = (
            df.withColumn("words",
                split(lower(regexp_replace(col("text"), "[^a-zA-Z\\s]", "")), "\\s+"))
            .withColumn("filtered",
                expr("filter(words, x -> length(x) > 3)"))
            .withColumn("keywords",
                concat_ws(", ", slice(array_distinct(col("filtered")), 1, 5)))
            .select("tmdb_id", "keywords")
            .filter(col("keywords") != "")
        )
        return {row["tmdb_id"]: row["keywords"] for row in processed_df.collect()}

    def close(self):
        if self.spark:
            self.spark.stop()
