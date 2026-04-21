from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Movie:
    # --- Source Maîtresse : TMDB ---
    tmdb_id: int
    title: str
    overview: Optional[str] = None
    release_date: Optional[str] = None
    vote_average: Optional[float] = None
    popularity: Optional[float] = None
    poster_path: Optional[str] = None
    
    # --- Enrichissement 1 : Rotten Tomatoes ---
    rt_tomatometer_score: Optional[int] = None
    rt_audience_score: Optional[int] = None
    rt_critics_consensus: Optional[str] = None
    
    # --- Enrichissement 2 : Kaggle (Détails littéraires) ---
    kaggle_literary_details: Optional[str] = None
    kaggle_synopsis: Optional[str] = None
    
    # --- Enrichissement 3 : IMDB ---
    imdb_id: Optional[str] = None
    imdb_rating: Optional[float] = None
    imdb_actors: Optional[str] = None
    imdb_director: Optional[str] = None
    casting: List[str] = field(default_factory=list)
    trivia: List[str] = field(default_factory=list)
    
    # --- Enrichissement 4 : Spark Data (Analyses textuelles) ---
    spark_text_analysis: Optional[dict] = None # Ou un objet plus spécifique
    spark_extracted_keywords: Optional[str] = None
    
    def __post_init__(self):
        """Initialisation et normalisation automatique."""
        self.normalize_date()
        self.clean_texts()

    def normalize_date(self):
        """Normalise la date au format ISO 8601 (YYYY-MM-DD)."""
        date_str = self.release_date
        if date_str and len(date_str) == 4 and date_str.isdigit():
            self.release_date = f"{date_str}-01-01"
            
    def clean_texts(self):
        """Nettoyage basique des textes (espaces, UTF-8)."""
        if isinstance(self.title, str):
            self.title = self.title.strip()
        if isinstance(self.overview, str):
            self.overview = self.overview.strip()

    def get_summary(self) -> str:
        """Retourne un résumé textuel pour le futur RAG."""
        summary = f"Titre: {self.title}\n"
        summary += f"Date de sortie: {self.release_date}\n"
        summary += f"Résumé: {self.overview}\n"
        
        if self.rt_tomatometer_score:
            summary += f"Score Rotten Tomatoes: {self.rt_tomatometer_score}%\n"
        
        if self.vote_average:
            summary += f"Note moyenne (TMDB): {self.vote_average}/10\n"
            
        return summary

    def __str__(self):
        return f"Movie(title='{self.title}', tmdb_id={self.tmdb_id}, imdb_id='{self.imdb_id}')"
