import logging
import os
from typing import List
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, regexp_replace, split, concat_ws, explode, length, collect_list, row_number
from pyspark.sql.window import Window

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

    def _top5_keywords(self, df, id_col: str) -> dict:
        """Extrait les 5 mots les plus fréquents par film (fréquence réelle)."""
        window = Window.partitionBy("tmdb_id").orderBy(col("cnt").desc())
        result = (
            df.select(col(id_col).cast("integer").alias("tmdb_id"),
                      regexp_replace(lower(col("overview")), "[^a-zA-Z\\s]", "").alias("text"))
            .filter(col("text").isNotNull() & (col("text") != ""))
            .withColumn("word", explode(split(col("text"), "\\s+")))
            .filter(length(col("word")) > 3)
            .groupBy("tmdb_id", "word").count().withColumnRenamed("count", "cnt")
            .withColumn("rn", row_number().over(window))
            .filter(col("rn") <= 5)
            .groupBy("tmdb_id").agg(concat_ws(", ", collect_list("word")).alias("keywords"))
        )
        return {row["tmdb_id"]: row["keywords"] for row in result.collect()}

    def _process_from_parts(self) -> dict:
        """Lit les fichiers CSV partitionnés avec Spark et extrait les mots-clés par fréquence."""
        logger.info("Spark : lecture de %s/*.csv ...", PARTS_DIR)
        df = self.spark.read.option("header", "true").option("inferSchema", "true").csv(f"{PARTS_DIR}/*.csv")
        id_col = "id" if "id" in df.columns else df.columns[0]
        return self._top5_keywords(df, id_col)

    def _process_from_memory(self, movies: List[TMDBMovie], kaggle_data: List[KaggleData]) -> dict:
        """Fallback : traitement depuis les objets en mémoire, mots-clés par fréquence."""
        kaggle_map = {k.tmdb_id: k.synopsis for k in kaggle_data if k.synopsis}
        data = [(m.tmdb_id, kaggle_map.get(m.tmdb_id) or m.overview or "") for m in movies]

        df = self.spark.createDataFrame(data, ["tmdb_id", "overview"])
        return self._top5_keywords(df, "tmdb_id")

    def close(self):
        if self.spark:
            self.spark.stop()
