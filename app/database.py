import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from app.models import Base

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("SUPABASE_DB_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
    logger.info("Connexion etablie avec Supabase (PostgreSQL).")
else:
    os.makedirs("data/db", exist_ok=True)
    db_path = "sqlite:///data/db/horror_movies.db"  # DB principale (pipeline)
    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    logger.info("SUPABASE_DB_URL manquante. Utilisation de SQLite : %s", db_path)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Fournit une session de base de données."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
