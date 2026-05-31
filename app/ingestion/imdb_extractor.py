import sqlite3
import os
from typing import List, Optional

# On importe uniquement Movie (le modèle unifié)
try:
    from app.models import Movie
except ImportError:
    from models import Movie

class IMDBExtractor:
    def __init__(self, db_path: str = "data/imdb.db"):
        self.db_path = db_path
        # S'assure que le dossier parent existe
        if os.path.dirname(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        if not os.path.exists(self.db_path):
            print(f"⚠️ Base IMDB introuvable : {self.db_path}")
            self.conn = None
        else:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            # Optimisations SQLite pour la performance en lecture
            self.conn.execute("PRAGMA journal_mode = OFF")
            self.conn.execute("PRAGMA synchronous = OFF")
            self.conn.execute("PRAGMA cache_size = -2000") # Utilise environ 2Mo de RAM pour le cache
            print(f"✅ Connecté à la base IMDB : {self.db_path}")

    def enrich_movies(self, movies: List[Movie]) -> List[Movie]:
        """Enrichit massivement les films avec Casting et Ratings IMDB."""
        if not self.conn or not movies:
            return movies

        cursor = self.conn.cursor()
        count = 0

        for movie in movies:
            try:
                # 1. Résolution de l'ID IMDB si manquant (via titre et année)
                if not movie.imdb_id:
                    year = movie.release_date.year if movie.release_date else None
                    sql = "SELECT tconst FROM title_basics WHERE primaryTitle = ? AND titleType = 'movie'"
                    params = [movie.title]
                    if year:
                        sql += " AND startYear = ?"
                        params.append(str(year))
                    
                    cursor.execute(sql, params)
                    result = cursor.fetchone()
                    if result:
                        movie.imdb_id = result['tconst']

                if not movie.imdb_id:
                    continue

                # 2. Récupération de la Note IMDB
                cursor.execute('SELECT averageRating, numVotes FROM title_ratings WHERE tconst = ?', (movie.imdb_id,))
                rating_row = cursor.fetchone()
                if rating_row:
                    movie.imdb_rating = float(rating_row['averageRating'])
                    movie.num_votes = int(rating_row['numVotes'])

                # 3. Récupération du Casting (Acteurs) et Réalisateur
                # Utilisation des nouveaux noms d'attributs du modèle unifié
                movie.actors = self._get_principals(cursor, movie.imdb_id, ('actor', 'actress', 'self'))
                movie.director = self._get_principals(cursor, movie.imdb_id, ('director',))
                
                count += 1
                if count % 1000 == 0:
                    print(f"   🎬 IMDB : {count} films enrichis...")

            except Exception:
                continue

        print(f"✅ Fin de l'étape IMDB : {count} films mis à jour.")
        return movies
        
    def _get_principals(self, cursor, tconst: str, categories: tuple) -> Optional[str]:
        """Récupère les noms des personnes par catégorie, triés par importance."""
        placeholders = ','.join('?' for _ in categories)
        query = f'''
            SELECT n.primaryName 
            FROM title_principals p
            JOIN name_basics n ON p.nconst = n.nconst
            WHERE p.tconst = ? AND p.category IN ({placeholders})
            ORDER BY p.ordering ASC
            LIMIT 5
        '''
        try:
            cursor.execute(query, [tconst] + list(categories))
            names = [row['primaryName'] for row in cursor.fetchall()]
            return ", ".join(names) if names else None
        except sqlite3.Error:
            return None

    def close(self):
        if self.conn:
            self.conn.close()