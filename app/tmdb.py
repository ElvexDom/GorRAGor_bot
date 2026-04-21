import requests
import os
import time
from dotenv import load_dotenv
try:
    from app.models import Movie
except ImportError:
    from models import Movie
from typing import List, Optional

# Charger les variables d'environnement
load_dotenv()

class TMDBIngestor:
    def __init__(self):
        token = os.getenv("TMDB_TOKEN")
        if not token:
            raise ValueError("TMDB_TOKEN manquant dans le fichier .env")
        
        self.token = token.strip()
        self.base_url = "https://api.themoviedb.org/3"
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        # Genre ID pour l'horreur
        self.horror_genre_id = 27

    def get_movie_imdb_id(self, tmdb_id: int) -> Optional[str]:
        """Récupère l'IMDB ID d'un film spécifique via l'endpoint external_ids."""
        url = f"{self.base_url}/movie/{tmdb_id}/external_ids"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("imdb_id")
        except Exception as e:
            print(f"Erreur lors de la récupération de l'IMDB ID pour {tmdb_id}: {e}")
            return None

    def fetch_horror_movies(self, max_pages: Optional[int] = None) -> List[Movie]:
        """
        Récupère les films d'horreur page par page depuis l'endpoint discover.
        Retourne une liste d'objets Movie (modèle unifié).
        """
        url = f"{self.base_url}/discover/movie"
        movies = []
        
        # Premier appel pour connaître le nombre total de pages
        params = {
            "with_genres": self.horror_genre_id
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            total_pages = data.get("total_pages", 0)
            
            # Limite TMDB : on ne peut pas aller au-delà de 500 pages via discover
            max_available = min(total_pages, 500)
            
            if max_pages:
                limit = min(max_available, max_pages)
            else:
                limit = max_available
                
            print(f"🎬 Début de la récupération : {limit} pages à traiter (Total dispo : {total_pages}).")
            
            for page in range(1, limit + 1):
                if page > 1: # On a déjà les données de la page 1
                    params["page"] = page
                    response = requests.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                
                results = data.get("results", [])
                if not results:
                    break
                    
                print(f"📥 Page {page}/{limit} : {len(results)} films trouvés.")
                
                for m in results:
                    tmdb_id = m.get("id")
                    print(f"   🎬 Traitement de {m.get('title')} ({tmdb_id})...")
                    imdb_id = self.get_movie_imdb_id(tmdb_id)
                    
                    # Création de l'objet Movie avec les données TMDB (Source Maîtresse)
                    # Les autres champs (RT, Kaggle, etc.) restent à None pour l'instant
                    movie = Movie(
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        title=m.get("title", ""),
                        overview=m.get("overview", ""),
                        release_date=m.get("release_date", ""),
                        vote_average=float(m.get("vote_average", 0.0)),
                        popularity=float(m.get("popularity", 0.0)),
                        poster_path=m.get("poster_path")
                    )
                    movies.append(movie)
                
                time.sleep(0.2)
                
        except Exception as e:
            print(f"Erreur lors de la récupération : {e}")
            
        return movies

if __name__ == "__main__":
    ingestor = TMDBIngestor()
    horror_movies = ingestor.fetch_horror_movies(max_pages=2) # Test limité
    
    print(f"\n✅ Terminé ! Total récupéré : {len(horror_movies)} objets Movie.")
    if horror_movies:
        first_movie = horror_movies[0]
        print(f"Propriétés du modèle unifié : {first_movie.title}")
        print(f" - TMDB ID: {first_movie.tmdb_id}")
        print(f" - IMDB ID: {first_movie.imdb_id}")
        print(f" - RT Score (actuellement None): {first_movie.rt_tomatometer_score}")