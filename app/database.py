import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker
try:
    from app.models import Movie as DataclassMovie
except ImportError:
    from models import Movie as DataclassMovie

# On charge l'URL de connexion Supabase (PostgreSQL) depuis l'environnement
# Format attendu : postgresql://postgres.[project-ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
DATABASE_URL = os.getenv("SUPABASE_DB_URL")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # Fallback pour le dev local si l'URL n'est pas fournie
    print("⚠️ SUPABASE_DB_URL non trouvée. Utilisation d'une base SQLite locale (data/local_dev.db)")
    os.makedirs("data", exist_ok=True)
    engine = create_engine("sqlite:///data/local_dev.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class DBMovie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, unique=True, index=True)
    imdb_id = Column(String(20), unique=True, index=True, nullable=True)
    title = Column(String, index=True)
    release_date = Column(String)
    
    # TMDB
    tmdb_overview = Column(Text, nullable=True)
    tmdb_popularity = Column(Float, nullable=True)
    
    # RT
    rt_tomatometer_score = Column(Integer, nullable=True)
    rt_audience_score = Column(Integer, nullable=True)
    rt_critics_consensus = Column(Text, nullable=True)
    
    # Kaggle
    kaggle_synopsis = Column(Text, nullable=True)
    kaggle_literary_details = Column(Text, nullable=True)
    
    # IMDB
    imdb_rating = Column(Float, nullable=True)
    imdb_actors = Column(Text, nullable=True)
    imdb_director = Column(Text, nullable=True)
    
    # Spark
    spark_extracted_keywords = Column(Text, nullable=True)

    @staticmethod
    def from_dataclass(movie: DataclassMovie) -> "DBMovie":
        return DBMovie(
            tmdb_id=movie.tmdb_id,
            imdb_id=movie.imdb_id,
            title=movie.title,
            release_date=movie.release_date,
            tmdb_overview=movie.overview,
            tmdb_popularity=movie.popularity,
            rt_tomatometer_score=movie.rt_tomatometer_score,
            rt_audience_score=movie.rt_audience_score,
            rt_critics_consensus=movie.rt_critics_consensus,
            kaggle_synopsis=movie.kaggle_synopsis,
            kaggle_literary_details=movie.kaggle_literary_details,
            imdb_rating=getattr(movie, 'imdb_rating', None),
            imdb_actors=getattr(movie, 'imdb_actors', None),
            imdb_director=getattr(movie, 'imdb_director', None),
            spark_extracted_keywords=getattr(movie, 'spark_extracted_keywords', None)
        )

# Création des tables si elles n'existent pas
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
