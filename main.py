import os
from dotenv import load_dotenv
from app.fusion_engine import DataOrchestrator
from app.database import SessionLocal, DBMovie

def main():
    # 1. Chargement des variables d'environnement (.env)
    load_dotenv()
    
    print("🎬 Initialisation du GorRAGor Bot...")
    
    # 2. Initialisation de l'orchestrateur
    # headless=True pour ne pas ouvrir de fenêtre navigateur pendant le scraping RT
    orchestrator = DataOrchestrator(headless_rt=True)
    
    try:
        # 3. Lancement du Pipeline
        # On peut ajuster max_pages selon les besoins (1 page = ~20 films)
        max_pages = int(os.getenv("PIPELINE_MAX_PAGES", 1))
        final_movies = orchestrator.run_pipeline(max_pages=max_pages)
        
        if not final_movies:
            print("⚠️ Aucun film n'a été récupéré.")
            return

        # 4. Persistence des données dans la base de données
        print(f"\n💾 Sauvegarde de {len(final_movies)} films dans la base de données...")
        db = SessionLocal()
        try:
            for movie in final_movies:
                db_movie = DBMovie.from_dataclass(movie)
                # On utilise merge pour mettre à jour si le film existe déjà (basé sur tmdb_id)
                db.merge(db_movie)
            db.commit()
            print("✅ Sauvegarde terminée avec succès !")
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde en base : {e}")
            db.rollback()
        finally:
            db.close()

        print(f"\n🚀 Ingestion terminée ! Prêt pour le RAG.")
        
    except KeyboardInterrupt:
        print("\n🛑 Interruption par l'utilisateur.")
    except Exception as e:
        print(f"💥 Une erreur critique est survenue : {e}")
    finally:
        # 5. Fermeture propre des ressources
        orchestrator.close()

if __name__ == "__main__":
    main()
