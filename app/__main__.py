import os
import logging
from dotenv import load_dotenv

from app.fusion_engine import DataOrchestrator
from app.database import SessionLocal, DBMovie


# ----------------------------
# Logging configuration
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ----------------------------
# Main pipeline
# ----------------------------
def main():
    load_dotenv()

    logger.info("🚀 Initialisation du GorRAGor Bot...")

    # Initialisation orchestrateur
    orchestrator = DataOrchestrator(headless_rt=True)

    db = None

    try:
        # ----------------------------
        # 1. Récupération config
        # ----------------------------
        max_pages = int(os.getenv("PIPELINE_MAX_PAGES", 1))
        logger.info(f"⚙️ Max pages configuré : {max_pages}")

        # ----------------------------
        # 2. Lancement pipeline
        # ----------------------------
        logger.info("📡 Lancement du pipeline d'ingestion...")
        final_movies = orchestrator.run_pipeline(max_pages=max_pages)

        if not final_movies:
            logger.warning("⚠️ Aucun film récupéré.")
            return

        logger.info(f"🎬 {len(final_movies)} films récupérés.")

        # ----------------------------
        # 3. Sauvegarde DB
        # ----------------------------
        logger.info("💾 Connexion à la base de données...")
        db = SessionLocal()

        logger.info("💾 Sauvegarde des films en base...")

        for movie in final_movies:
            try:
                db_movie = DBMovie.from_dataclass(movie)
                db.merge(db_movie)
            except Exception as e:
                logger.error(f"❌ Erreur mapping film {movie}: {e}")

        db.commit()
        logger.info("✅ Sauvegarde terminée avec succès.")

        # ----------------------------
        # 4. Fin pipeline
        # ----------------------------
        logger.info("🎉 Ingestion terminée. Prêt pour le RAG.")

    except KeyboardInterrupt:
        logger.warning("⛔ Interruption utilisateur détectée.")

    except Exception as e:
        logger.exception(f"🔥 Erreur critique : {e}")
        if db:
            db.rollback()

    finally:
        # ----------------------------
        # 5. Cleanup
        # ----------------------------
        if db:
            db.close()
            logger.info("🧹 Connexion DB fermée.")

        orchestrator.close()
        logger.info("🧹 Orchestrateur fermé.")


# ----------------------------
# Entry point
# ----------------------------
if __name__ == "__main__":
    main()