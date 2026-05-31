import requests
import os
import time
import logging
from dotenv import load_dotenv
from typing import List
from app.models import TMDBMovie
from app.utils.normalizers import normalize_date, clean_txt

load_dotenv()
logger = logging.getLogger(__name__)


class TMDBIngestor:
    def __init__(self):
        token = os.getenv("TMDB_TOKEN")
        if not token:
            raise ValueError("TMDB_TOKEN manquant dans le .env")

        self.base_url = "https://api.themoviedb.org/3"
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "Authorization": f"Bearer {token.strip()}"
        })
        self.horror_genre_id = 27

    def fetch_horror_movies(self) -> List[TMDBMovie]:
        """Extraction des films d'horreur depuis TMDB (1874-2026)."""
        all_movies = []
        years = range(1874, 2027)

        for year in years:
            page = 1
            total_pages = 1

            while page <= total_pages and page <= 500:
                params = {
                    "with_genres": self.horror_genre_id,
                    "primary_release_year": year,
                    "include_adult": "false",
                    "page": page
                }
                try:
                    resp = self.session.get(f"{self.base_url}/discover/movie", params=params)
                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    total_pages = data.get("total_pages", 0)

                    for m in data.get("results", []):
                        all_movies.append(TMDBMovie(
                            tmdb_id       = m.get("id"),
                            title         = m.get("title"),
                            original_title= m.get("original_title"),
                            release_date  = normalize_date(m.get("release_date")),
                            overview      = clean_txt(m.get("overview")),
                            popularity    = m.get("popularity"),
                            vote_average  = m.get("vote_average"),
                            vote_count    = m.get("vote_count"),
                            poster_path   = m.get("poster_path"),
                            backdrop_path = m.get("backdrop_path"),
                        ))
                    page += 1
                except Exception as e:
                    logger.warning("Erreur TMDB annee %s page %s : %s", year, page, e)
                    break

            logger.info("TMDB %s : %d films collectes au total.", year, len(all_movies))
            time.sleep(0.02)

        # Dédoublonnage par tmdb_id (un même film peut apparaître sur plusieurs années)
        seen = {}
        for m in all_movies:
            seen[m.tmdb_id] = m
        unique_movies = list(seen.values())
        logger.info("TMDB : %d films uniques apres dedoublonnage (sur %d).",
                    len(unique_movies), len(all_movies))
        return unique_movies
