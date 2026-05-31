import sys
import logging
import argparse

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from app.fusion_engine import DataOrchestrator
from app.database import SessionLocal, engine
from app.models import Base, TMDBMovie, KaggleData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def init_db():
    logger.info("Verification et initialisation de la base de donnees...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Base de donnees prete (tables verifiees/creees).")
    except Exception as e:
        logger.error("Erreur initialisation DB : %s", e)
        raise


def sync_db(db, records):
    """Sauvegarde ou met à jour une liste d'objets SQLAlchemy en base."""
    if not records:
        logger.warning("Aucun enregistrement a synchroniser.")
        return

    logger.info("Synchronisation de %d enregistrements...", len(records))
    saved = 0
    for i, record in enumerate(records):
        try:
            db.merge(record)
            if (i + 1) % 500 == 0:
                db.commit()
                saved = i + 1
                logger.info("  %d enregistrements synchronises...", saved)
        except Exception as e:
            db.rollback()
            logger.warning("Doublon ignore (enregistrement %d) : %s", i, e)
            # Remet les enregistrements déjà mergés dans la session
            for r in records[saved:i]:
                try:
                    db.merge(r)
                except Exception:
                    pass

    db.commit()
    logger.info("Synchronisation terminee.")


def load_tmdb_movies(db) -> list:
    logger.info("Chargement des films depuis tmdb_movies...")
    return db.query(TMDBMovie).all()


def load_kaggle_data(db) -> list:
    return db.query(KaggleData).all()


def main():
    load_dotenv()
    init_db()

    parser = argparse.ArgumentParser(description="Pipeline de donnees GorRAGor-Bot")
    parser.add_argument("--tmdb",   action="store_true", help="Phase 0 : Ingestion TMDB (Source Maitresse)")
    parser.add_argument("--rt",     action="store_true", help="Phase 1 : Enrichissement Rotten Tomatoes")
    parser.add_argument("--kaggle", action="store_true", help="Phase 2 : Enrichissement Kaggle (CSV)")
    parser.add_argument("--imdb",   action="store_true", help="Phase 3 : Enrichissement IMDB (SQLite)")
    parser.add_argument("--spark",  action="store_true", help="Phase 4 : Analyse NLP Spark")
    parser.add_argument("--all",    action="store_true", help="Lancer tout le pipeline")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return

    orchestrator = DataOrchestrator()
    db = SessionLocal()
    tmdb_movies = []
    kaggle_data = []

    try:
        if args.tmdb or args.all:
            logger.info("SOURCE : Ingestion TMDB...")
            tmdb_movies = orchestrator.ingest_tmdb()
            sync_db(db, tmdb_movies)

        if args.rt or args.all:
            if not tmdb_movies:
                tmdb_movies = load_tmdb_movies(db)
            logger.info("ENRICH 1 : Scraping Rotten Tomatoes...")
            rt_scores = orchestrator.enrich_with_rt(tmdb_movies)
            sync_db(db, rt_scores)

        if args.kaggle or args.all:
            if not tmdb_movies:
                tmdb_movies = load_tmdb_movies(db)
            logger.info("ENRICH 2 : Fusion Kaggle...")
            kaggle_data = orchestrator.enrich_with_kaggle(tmdb_movies)
            sync_db(db, kaggle_data)

        if args.imdb or args.all:
            if not tmdb_movies:
                tmdb_movies = load_tmdb_movies(db)
            logger.info("ENRICH 3 : Ingestion IMDB...")
            imdb_data = orchestrator.enrich_with_imdb(tmdb_movies)
            sync_db(db, imdb_data)

        if args.spark or args.all:
            if not tmdb_movies:
                tmdb_movies = load_tmdb_movies(db)
            if not kaggle_data:
                kaggle_data = load_kaggle_data(db)
            logger.info("ENRICH 4 : Analyse Spark...")
            spark_data = orchestrator.enrich_with_spark(tmdb_movies, kaggle_data)
            sync_db(db, spark_data)

    except KeyboardInterrupt:
        logger.warning("Interruption utilisateur. Arret propre...")
    except Exception as e:
        logger.exception("ERREUR CRITIQUE DANS LE PIPELINE : %s", e)
    finally:
        db.close()
        orchestrator.close()
        logger.info("Ressources liberees. Fin du processus.")


if __name__ == "__main__":
    main()
