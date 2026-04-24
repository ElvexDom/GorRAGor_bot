import polars as pl
import os
from typing import List

try:
    from app.models import Movie
except ImportError:
    from models import Movie

class KaggleIngestor:
    def __init__(self, csv_path: str = "data/raw/horror_movies.csv"):
        self.csv_path = csv_path
        self.df = None
        
        if not os.path.exists(self.csv_path):
            print(f"⚠️ Fichier Kaggle non trouvé : {self.csv_path}")
            return

        try:
            # On lit tout le CSV
            self.df = pl.read_csv(self.csv_path, infer_schema_length=10000)
            
            # Mapping : Colonne 0 = index (""), Colonne 1 = "id" (TMDB ID)
            self.id_col = self.df.columns[1]
            
            # Conversion date pour compatibilité Scraper
            if "release_date" in self.df.columns:
                self.df = self.df.with_columns(
                    pl.col("release_date").str.to_date(format="%Y-%m-%d", strict=False)
                )
            
            print(f"✅ KaggleIngestor prêt. (Mapping colonne: '{self.id_col}')")
        except Exception as e:
            print(f"❌ Erreur lecture CSV : {e}")

    def enrich_movies(self, movies: List[Movie]) -> List[Movie]:
        """Fusionne les données Kaggle avec les objets Movie fournis."""
        if self.df is None or not movies:
            return movies

        # Dictionnaire d'indexation pour accès O(1)
        kaggle_dict = {}
        for row in self.df.to_dicts():
            try:
                # Nettoyage et conversion de l'ID du CSV
                raw_id = row.get(self.id_col)
                if raw_id:
                    clean_id = int(float(str(raw_id).strip().replace('"', '')))
                    kaggle_dict[clean_id] = row
            except:
                continue

        count = 0
        for movie in movies:
            try:
                search_id = int(float(str(movie.tmdb_id).strip()))
            except:
                search_id = None

            data = kaggle_dict.get(search_id)
            
            if data:
                # Enrichissement du synopsis et des métadonnées littéraires
                movie.kaggle_synopsis = data.get("overview")
                
                g = data.get("genre_names", "")
                t = data.get("tagline", "")
                r = data.get("runtime", "")
                
                details = []
                if g: details.append(f"Genres: {g}")
                if t: details.append(f"Tagline: {t}")
                if r: details.append(f"Durée: {r} min")
                
                movie.kaggle_literary_details = " | ".join(details)
                count += 1

        print(f"📊 Enrichissement Kaggle : {count}/{len(movies)} films complétés.")
        return movies