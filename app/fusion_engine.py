from typing import List
try:
    from app.models import Movie
    from app.tmdb import TMDBIngestor
    from app.rt_scraper import RTScraper
    from app.imdb_extract import IMDBExtractor
except ImportError:
    from models import Movie
    from tmdb import TMDBIngestor
    from rt_scraper import RTScraper
    from imdb_extract import IMDBExtractor

class DataOrchestrator:
    def __init__(self, headless_rt=True):
        self.tmdb_ingestor = TMDBIngestor()
        self.rt_scraper = RTScraper(headless=headless_rt)
        self.imdb_extractor = IMDBExtractor()

    def run_pipeline(self, max_pages: int = 1) -> List[Movie]:
        print("🚀 Démarrage du Pipeline d'Ingestion HorRAGor...")
        
        # 1. Extraction maître (TMDB)
        print("\n--- 1. TMDB (Source Maître) ---")
        movies = self.tmdb_ingestor.fetch_horror_movies(max_pages=max_pages)
        print(f"✅ {len(movies)} films récupérés via TMDB.")

        # 2. Enrichissement (IMDB) - Plus rapide, donc fait en premier
        print("\n--- 2. IMDB (Base locale) ---")
        movies = self.imdb_extractor.enrich_movies(movies)

        # 3. Enrichissement (Rotten Tomatoes) - Scraping (plus lent)
        print("\n--- 3. Rotten Tomatoes (Scraping) ---")
        for movie in movies:
            self.rt_scraper.search_and_enrich(movie)
            
        print("\n🎉 Pipeline terminé avec succès !")
        return movies
        
    def generate_rag_documents(self, movies: List[Movie]):
        """Génère les textes enrichis pour le RAG."""
        docs = []
        for m in movies:
            docs.append(m.get_summary())
        return docs

    def close(self):
        self.rt_scraper.close()
        self.imdb_extractor.close()

if __name__ == "__main__":
    # Test complet de bout en bout
    orchestrator = DataOrchestrator(headless_rt=True)
    try:
        # On limite à 1 page (20 films max) pour tester
        final_movies = orchestrator.run_pipeline(max_pages=1)
        
        print("\n--- Aperçu des données pour le RAG ---")
        if final_movies:
            print(final_movies[0].get_summary())
            
    finally:
        orchestrator.close()
