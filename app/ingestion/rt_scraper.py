import re
import urllib.parse
import time
import logging
from typing import List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from app.models import TMDBMovie, RTScore
from app.utils.normalizers import clean_txt

logger = logging.getLogger(__name__)


class RTScraper:
    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.wait = WebDriverWait(self.driver, 10)

    def scrape_movie(self, movie: TMDBMovie) -> RTScore | None:
        """Scrape RT pour un film. Retourne RTScore ou None si non trouvé."""
        year = movie.release_date.year if movie.release_date else ""
        query = f"{movie.title} {year}".strip()
        search_url = f"https://www.rottentomatoes.com/search?search={urllib.parse.quote(query)}"

        try:
            self.driver.get(search_url)
            try:
                movie_link = self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'search-page-result[type="movie"] a[data-qa="info-name"]')
                    )
                )
                self.driver.get(movie_link.get_attribute("href"))
            except Exception:
                return None

            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            scores = self.driver.execute_script("""
                let res = { tomatometer: null, audience: null, consensus: null };
                const sb = document.querySelector('score-board, rt-score-card');
                if (sb) {
                    res.tomatometer = sb.getAttribute('tomatometerscore') || sb.getAttribute('critics-score');
                    res.audience = sb.getAttribute('audiencescore') || sb.getAttribute('audience-score');
                }
                const con = document.querySelector(
                    '[data-qa="critics-consensus"], rt-text[slot="critics-consensus"]'
                );
                if (con) res.consensus = con.innerText;
                return res;
            """)

            def to_int(s):
                if s is None:
                    return None
                digits = re.sub(r'\D', '', str(s))
                return int(digits) if digits else None

            audience = to_int(scores.get('audience'))
            if audience is None:
                match = re.search(r'audience-score="(\d+)"', self.driver.page_source)
                if match:
                    audience = int(match.group(1))

            return RTScore(
                tmdb_id           = movie.tmdb_id,
                tomatometer_score = to_int(scores.get('tomatometer')),
                audience_score    = audience,
                critics_consensus = clean_txt(scores.get('consensus')),
            )

        except Exception as e:
            logger.warning("Erreur RT (%s) : %s", movie.title, e)
            return None

    def scrape_all(self, movies: List[TMDBMovie]) -> List[RTScore]:
        """Scrape RT pour une liste de films. Retourne uniquement les scores trouvés."""
        results = []
        for i, movie in enumerate(movies):
            if i % 10 == 0:
                logger.info("RT : %d/%d films traites...", i, len(movies))
            score = self.scrape_movie(movie)
            if score:
                results.append(score)
            time.sleep(0.5)
        return results

    def close(self):
        self.driver.quit()
