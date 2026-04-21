import sqlite3
import os
from typing import List, Optional
try:
    from app.models import Movie
except ImportError:
    from models import Movie

class IMDBExtractor:
    def __init__(self, db_path: str = "data/imdb.db"):
        self.db_path = db_path
        # Assurez-vous que le dossier data existe
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Test de connexion
        if not os.path.exists(self.db_path):
            print(f"⚠️ Base de données IMDB introuvable à l'emplacement : {self.db_path}")
            print("   L'extraction IMDB sera ignorée.")
            self.conn = None
        else:
            self.conn = sqlite3.connect(self.db_path)
            # On configure row_factory pour récupérer des dictionnaires
            self.conn.row_factory = sqlite3.Row
            print(f"✅ Connecté à la base IMDB : {self.db_path}")

    def enrich_movies(self, movies: List[Movie]) -> List[Movie]:
        """Enrichit la liste de films avec les informations IMDB (casting, trivia, note globale)."""
        if not self.conn:
            return movies

        print(f"🎬 Enrichissement IMDB en cours pour {len(movies)} films...")
        cursor = self.conn.cursor()

        for movie in movies:
            try:
                # 1. Identifier l'ID IMDB si on ne l'a pas encore fait
                if not movie.imdb_id:
                    # Recherche approximative basée sur le titre exact (peut nécessiter d'être affinée)
                    query = '''
                        SELECT tconst FROM title_basics 
                        WHERE primaryTitle = ? AND titleType = 'movie'
                    '''
                    cursor.execute(query, (movie.title,))
                    result = cursor.fetchone()
                    if result:
                        movie.imdb_id = result['tconst']

                if not movie.imdb_id:
                    continue  # Toujours pas d'ID, on passe au suivant

                # 2. Récupérer la note moyenne
                cursor.execute('SELECT averageRating FROM title_ratings WHERE tconst = ?', (movie.imdb_id,))
                rating_row = cursor.fetchone()
                if rating_row:
                    movie.imdb_rating = float(rating_row['averageRating'])

                # 3. Récupérer le casting principal (acteurs et réalisateurs)
                movie.imdb_actors = self._get_principals(cursor, movie.imdb_id, ('actor', 'actress'))
                movie.imdb_director = self._get_principals(cursor, movie.imdb_id, ('director',))
                
                print(f"   ✨ Enrichi (IMDB) : {movie.title} - Note: {movie.imdb_rating}")

            except Exception as e:
                print(f"   ⚠️ Erreur IMDB pour {movie.title} : {e}")

        return movies
        
    def _get_principals(self, cursor, tconst: str, categories: tuple) -> Optional[str]:
        """Récupère les noms des personnes par catégorie."""
        # Note: Supposant la structure standard des datasets IMDB (title.principals, name.basics)
        # S'adapte selon votre schéma SQLite réel
        placeholders = ','.join('?' for _ in categories)
        query = f'''
            SELECT n.primaryName 
            FROM title_principals p
            JOIN name_basics n ON p.nconst = n.nconst
            WHERE p.tconst = ? AND p.category IN ({placeholders})
            LIMIT 5
        '''
        params = [tconst] + list(categories)
        try:
            cursor.execute(query, params)
            names = [row['primaryName'] for row in cursor.fetchall()]
            return ", ".join(names) if names else None
        except sqlite3.OperationalError:
            # Si les tables ne sont pas encore prêtes/importées
            return None

    def close(self):
        if self.conn:
            self.conn.close()

if __name__ == "__main__":
    extractor = IMDBExtractor()
    test_movie = Movie(tmdb_id=0, title="The Exorcist", imdb_id="tt0070047")
    enriched = extractor.enrich_movies([test_movie])
    print(f"\nRésultat final IMDB : {enriched[0]}")
    extractor.close()
