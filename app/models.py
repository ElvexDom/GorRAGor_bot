from sqlalchemy import Column, Integer, String, Float, JSON, Date, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import re

Base = declarative_base()

class Movie(Base):
    __tablename__ = 'movies'

    # --- SOURCE MAÎTRESSE : TMDB (Identifiants & Référence) ---
    tmdb_id = Column(Integer, primary_key=True)
    imdb_id = Column(String(20), index=True, nullable=True) # Niveau de matching 2
    title = Column(String(255), nullable=False)
    original_title = Column(String(255))
    overview = Column(Text)
    release_date = Column(Date) # Normalisé ISO 8601
    vote_average = Column(Float)
    vote_count = Column(Integer)
    popularity = Column(Float)
    poster_path = Column(String(255))
    backdrop_path = Column(String(255))

    # --- ENRICHISSEMENT 1 : ROTTEN TOMATOES (Scraping) ---
    rt_tomatometer_score = Column(Integer) # Conservé en base 100 selon consignes
    rt_audience_score = Column(Integer)
    rt_critics_consensus = Column(Text)

    # --- ENRICHISSEMENT 2 : KAGGLE (Polars / Littérature) ---
    budget = Column(Float)
    revenue = Column(Float)
    kaggle_synopsis = Column(Text)

    # --- ENRICHISSEMENT 3 : IMDB (SQLite / Seuil Qualité) ---
    imdb_rating = Column(Float)
    num_votes = Column(Integer) # Pour filtrage >= 1000
    director = Column(String(255))
    actors = Column(Text) # Liste d'acteurs concaténée

    # --- ENRICHISSEMENT 4 : SPARK DATA (Analyses NLP) ---
    spark_analysis = Column(JSON)
    spark_extracted_keywords = Column(Text)

    def normalize_date(self, date_str):
        """Normalise les dates hétérogènes au format ISO 8601 (YYYY-MM-DD)."""
        if not date_str:
            return None
        try:
            # Gestion YYYY seul (Kaggle/IMDB) -> YYYY-01-01
            if len(str(date_str)) == 4:
                return datetime.strptime(f"{date_str}-01-01", "%Y-%m-%d").date()
            # Gestion YYYY-MM-DD (TMDB)
            return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def clean_texts(self):
        """Nettoyage : suppression HTML, espaces superflus et conversion UTF-8."""
        for attr in ['title', 'overview', 'rt_critics_consensus', 'kaggle_synopsis']:
            val = getattr(self, attr)
            if val and isinstance(val, str):
                # Suppression des balises HTML
                clean_val = re.sub(r'<[^>]+>', '', val)
                # Trim et normalisation des espaces
                setattr(self, attr, " ".join(clean_val.split()))

    def get_summary(self) -> str:
        """Bloc de texte optimisé pour le futur RAG (Fallback logic)."""
        # Priorité TMDB > Kaggle pour la description
        desc = self.overview if self.overview else (self.kaggle_synopsis if self.kaggle_synopsis else "N/A")
        
        return (
            f"Titre: {self.title}\n"
            f"Sortie: {self.release_date}\n"
            f"Réalisateur: {self.director}\n"
            f"Description: {desc}\n"
            f"Note TMDB: {self.vote_average}/10 | Note IMDB: {self.imdb_rating}/10\n"
            f"Consensus: {self.rt_critics_consensus}"
        )