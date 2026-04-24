from typing import List
from app.models import Movie
from app.tmdb import TMDBIngestor
from app.rt_scraper import RTScraper
from app.kaggle_ingest import KaggleIngestor

class DataOrchestrator:
    def __init__(self, headless_rt=True):
        self.tmdb_ingestor = TMDBIngestor()
        self.rt_scraper = RTScraper(headless=headless_rt)
        self.kaggle_ingestor = KaggleIngestor()

    def ingest_tmdb(self) -> List[Movie]:
        """Phase 1 : Ingestion Maître."""
        print("\n--- [SOURCE: TMDB] ---")
        return self.tmdb_ingestor.fetch_horror_movies()

    def enrich_with_kaggle(self, movies: List[Movie]) -> List[Movie]:
        """Phase 2 : Enrichissement CSV local (Rapide)."""
        print("\n--- [ENRICHISSEMENT: KAGGLE] ---")
        return self.kaggle_ingestor.enrich_movies(movies)

    def enrich_with_rt(self, movies: List[Movie]) -> List[Movie]:
        """Phase 3 : Enrichissement Web Scraping (Lent)."""
        print("\n--- [ENRICHISSEMENT: ROTTEN TOMATOES] ---")
        for i, movie in enumerate(movies):
            if i % 20 == 0:
                print(f"📊 Scraping RT : {i}/{len(movies)} films traités...")
            self.rt_scraper.search_and_enrich(movie)
        return movies

    def close(self):
        self.rt_scraper.close()