import os
import re
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Date, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Configuration de l'URL Supabase
DATABASE_URL = os.getenv("SUPABASE_DB_URL")

if DATABASE_URL:
    # On force l'utilisation du driver psycopg2 pour PostgreSQL
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    print("⚠️ SUPABASE_DB_URL non trouvée. Repli sur SQLite local.")
    os.makedirs("data", exist_ok=True)
    engine = create_engine("sqlite:///data/sqlite/movies.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class DBMovie(Base):
    __tablename__ = "movies"

    # --- Identifiants & MDM ---
    # On utilise tmdb_id comme clé primaire réelle car c'est la source maîtresse
    tmdb_id = Column(Integer, primary_key=True, index=True)
    imdb_id = Column(String(20), unique=True, index=True, nullable=True) # Matching Niveau 2
    
    # --- Identité & TMDB ---
    title = Column(String, index=True, nullable=False)
    original_title = Column(String, nullable=True)
    release_date = Column(Date, nullable=True) # Format ISO 8601 imposé
    tmdb_overview = Column(Text, nullable=True)
    tmdb_popularity = Column(Float, nullable=True)
    tmdb_vote_average = Column(Float, nullable=True)
    tmdb_vote_count = Column(Integer, nullable=True)
    poster_path = Column(String, nullable=True)
    backdrop_path = Column(String, nullable=True)
    
    # --- Enrichissement 1 : Rotten Tomatoes ---
    rt_tomatometer_score = Column(Integer, nullable=True)
    rt_audience_score = Column(Integer, nullable=True)
    rt_critics_consensus = Column(Text, nullable=True)
    
    # --- Enrichissement 2 : Kaggle ---
    kaggle_synopsis = Column(Text, nullable=True)
    kaggle_literary_details = Column(Text, nullable=True)
    budget = Column(Float, nullable=True)
    revenue = Column(Float, nullable=True)
    
    # --- Enrichissement 3 : IMDB ---
    imdb_rating = Column(Float, nullable=True)
    imdb_num_votes = Column(Integer, nullable=True) # Seuil qualité >= 1000
    imdb_actors = Column(Text, nullable=True)
    imdb_director = Column(Text, nullable=True)
    
    # --- Enrichissement 4 : Spark & NLP ---
    spark_extracted_keywords = Column(Text, nullable=True)
    spark_analysis_json = Column(JSON, nullable=True)

    @classmethod
    def from_dataclass(cls, movie_obj) -> "DBMovie":
        """
        Convertit l'objet métier (dataclass) en objet DB SQLAlchemy.
        Incorpore la logique de nettoyage et de normalisation des dates.
        """
        # Nettoyage HTML/Espaces (Normalisation des textes)
        def clean_txt(text):
            if not text: return None
            return " ".join(re.sub(r'<[^>]+>', '', str(text)).split()).strip()

        # Normalisation Date ISO 8601
        clean_date = None
        raw_date = getattr(movie_obj, 'release_date', None)
        if raw_date:
            try:
                if len(str(raw_date)) == 4: # YYYY -> YYYY-01-01
                    clean_date = datetime.strptime(f"{raw_date}-01-01", "%Y-%m-%d").date()
                else:
                    clean_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
            except:
                clean_date = None

        return cls(
            tmdb_id=movie_obj.tmdb_id,
            imdb_id=movie_obj.imdb_id,
            title=clean_txt(movie_obj.title),
            original_title=clean_txt(getattr(movie_obj, 'original_title', None)),
            release_date=clean_date,
            tmdb_overview=clean_txt(getattr(movie_obj, 'overview', None)),
            tmdb_popularity=movie_obj.popularity,
            tmdb_vote_average=getattr(movie_obj, 'vote_average', None),
            tmdb_vote_count=getattr(movie_obj, 'vote_count', None),
            poster_path=getattr(movie_obj, 'poster_path', None),
            backdrop_path=getattr(movie_obj, 'backdrop_path', None),
            rt_tomatometer_score=getattr(movie_obj, 'rt_tomatometer_score', None),
            rt_audience_score=getattr(movie_obj, 'rt_audience_score', None),
            rt_critics_consensus=clean_txt(getattr(movie_obj, 'rt_critics_consensus', None)),
            kaggle_synopsis=clean_txt(getattr(movie_obj, 'kaggle_synopsis', None)),
            kaggle_literary_details=clean_txt(getattr(movie_obj, 'kaggle_literary_details', None)),
            imdb_rating=getattr(movie_obj, 'imdb_rating', None),
            imdb_num_votes=getattr(movie_obj, 'num_votes', None),
            imdb_actors=clean_txt(getattr(movie_obj, 'imdb_actors', None)),
            imdb_director=clean_txt(getattr(movie_obj, 'imdb_director', None)),
            spark_extracted_keywords=getattr(movie_obj, 'spark_extracted_keywords', None)
        )

# Création des tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()