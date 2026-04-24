import requests
import os
import time
from dotenv import load_dotenv
from typing import List, Optional
from app.models import Movie

load_dotenv()

class TMDBIngestor:
    def __init__(self):
        token = os.getenv("TMDB_TOKEN")
        if not token:
            raise ValueError("TMDB_TOKEN manquant dans le .env")
        
        self.base_url = "https://api.themoviedb.org/3"
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "Authorization": f"Bearer {token.strip()}"
        })
        self.horror_genre_id = 27

    def get_movie_imdb_id(self, tmdb_id: int) -> Optional[str]:
        url = f"{self.base_url}/movie/{tmdb_id}/external_ids"
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("imdb_id")
            return None
        except Exception:
            return None

    def fetch_horror_movies(self) -> List[Movie]:
        """Récupère TOUTES les pages renvoyées par TMDB sans aucune limite."""
        url = f"{self.base_url}/discover/movie"
        all_movies = []
        params = {
            "with_genres": self.horror_genre_id,
            "sort_by": "popularity.desc",
            "page": 1
        }

        try:
            print(f"🚀 Initialisation TMDB (Mode Intégral)...")
            
            # 1. Première requête pour obtenir le total_pages dynamique
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            # On récupère ton 'total_pages' (3487 dans ton exemple)
            total_pages = data.get("total_pages", 0)
            total_results = data.get("total_results", 0)
            
            print(f"📊 {total_results} films trouvés.")
            print(f"📥 Extraction de la totalité des {total_pages} pages...")

            # 2. Boucle sur chaque page de 1 à total_pages
            for page in range(1, total_pages + 1):
                params["page"] = page
                
                page_resp = self.session.get(url, params=params)
                
                if page_resp.status_code != 200:
                    print(f"⚠️ Erreur page {page} ({page_resp.status_code}). Tentative d'arrêt propre.")
                    break

                page_data = page_resp.json()
                results = page_data.get("results", [])

                if not results:
                    break

                print(f"📄 Page {page}/{total_pages} en cours...")
                
                for m in results:
                    movie = Movie(
                        tmdb_id=m.get("id"),
                        title=m.get("title"),
                        original_title=m.get("original_title"),
                        overview=m.get("overview"),
                        vote_average=float(m.get("vote_average", 0.0)),
                        vote_count=int(m.get("vote_count", 0)),
                        popularity=float(m.get("popularity", 0.0)),
                        poster_path=m.get("poster_path"),
                        backdrop_path=m.get("backdrop_path")
                    )

                    movie.release_date = movie.normalize_date(m.get("release_date"))
                    # On récupère l'ID IMDB pour chaque film
                    movie.imdb_id = self.get_movie_imdb_id(movie.tmdb_id)
                    
                    if hasattr(movie, 'clean_texts'):
                        movie.clean_texts()
                    
                    all_movies.append(movie)
                
                # Délai court pour respecter l'API sur une longue durée
                time.sleep(0.1) 

        except Exception as e:
            print(f"❌ Erreur critique TMDB: {e}")
            
        return all_movies