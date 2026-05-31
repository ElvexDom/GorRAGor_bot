import logging
from typing import List

from app.models import TMDBMovie, RTScore, KaggleData, IMDBData, SparkAnalysis

logger = logging.getLogger(__name__)


class DataOrchestrator:
    """
    Orchestrateur du pipeline d'ingestion.
    Initialisation paresseuse : chaque moteur n'est créé qu'au moment où il est utilisé.
    """

    def __init__(self, headless_rt=True):
        self._headless_rt = headless_rt
        self._tmdb   = None
        self._rt     = None
        self._kaggle = None
        self._imdb   = None
        self._spark  = None

    @property
    def tmdb(self):
        if self._tmdb is None:
            from app.ingestion.tmdb import TMDBIngestor
            self._tmdb = TMDBIngestor()
        return self._tmdb

    @property
    def rt(self):
        if self._rt is None:
            from app.ingestion.rt_scraper import RTScraper
            self._rt = RTScraper(headless=self._headless_rt)
        return self._rt

    @property
    def kaggle(self):
        if self._kaggle is None:
            from app.ingestion.kaggle_ingest import KaggleIngestor
            self._kaggle = KaggleIngestor()
        return self._kaggle

    @property
    def imdb(self):
        if self._imdb is None:
            from app.ingestion.imdb_extractor import IMDBExtractor
            self._imdb = IMDBExtractor()
        return self._imdb

    @property
    def spark(self):
        if self._spark is None:
            from app.ingestion.spark_processor import SparkProcessor
            self._spark = SparkProcessor()
        return self._spark

    def ingest_tmdb(self) -> List[TMDBMovie]:
        logger.info("--- [1/5 SOURCE: TMDB] ---")
        return self.tmdb.fetch_horror_movies()

    def enrich_with_rt(self, movies: List[TMDBMovie]) -> List[RTScore]:
        logger.info("--- [2/5 ENRICHISSEMENT: ROTTEN TOMATOES] ---")
        return self.rt.scrape_all(movies)

    def enrich_with_kaggle(self, movies: List[TMDBMovie]) -> List[KaggleData]:
        logger.info("--- [3/5 ENRICHISSEMENT: KAGGLE] ---")
        return self.kaggle.build_kaggle_data(movies)

    def enrich_with_imdb(self, movies: List[TMDBMovie]) -> List[IMDBData]:
        logger.info("--- [4/5 ENRICHISSEMENT: IMDB] ---")
        return self.imdb.build_imdb_data(movies)

    def enrich_with_spark(self, movies: List[TMDBMovie], kaggle_data: List[KaggleData]) -> List[SparkAnalysis]:
        logger.info("--- [5/5 ENRICHISSEMENT: SPARK] ---")
        # Partitionne le CSV Kaggle pour Spark si ce n'est pas déjà fait
        self.kaggle.split_for_spark()
        return self.spark.process(movies, kaggle_data)

    def close(self):
        try:
            if self._rt:    self._rt.close()
            if self._imdb:  self._imdb.close()
            if self._spark: self._spark.close()
            logger.info("Orchestrateur : moteurs utilises fermes proprement.")
        except Exception as e:
            logger.warning("Erreur lors de la fermeture : %s", e)
