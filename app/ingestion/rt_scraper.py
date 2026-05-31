from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
try:
    from app.models import Movie
except ImportError:
    from models import Movie
from typing import Optional
import time
import urllib.parse

class RTScraper:
    def __init__(self, headless=True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # Simuler un vrai navigateur
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Initialisation du driver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.wait = WebDriverWait(self.driver, 15)

    def search_and_enrich(self, movie: Movie) -> Movie:
        """Cherche le film sur RT et enrichit l'objet Movie avec les scores."""
        
        # --- MODIFICATION : UTILISATION EXCLUSIVE DE DATETIME.DATE ---
        year_str = str(movie.release_date.year) if movie.release_date else ""
        
        query = f"{movie.title} {year_str}".strip()
        search_url = f"https://www.rottentomatoes.com/search?search={urllib.parse.quote(query)}"
        
        print(f"🔍 Recherche RT pour : {query}...")
        
        try:
            self.driver.get(search_url)
            
            # Attente flexible pour les résultats de recherche
            try:
                # Tentative 1 : Sélecteur par défaut
                movie_link_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'search-page-result[type="movie"] a[data-qa="info-name"]'))
                )
            except Exception:
                # Tentative 2 : Repli sur n'importe quel lien de film
                print("   ⚠️ Sélecteur précis échoué, tentative de repli...")
                movie_link_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/m/"]'))
                )
            
            movie_url = movie_link_element.get_attribute("href")
            print(f"   🔗 Page trouvée : {movie_url}")
            self.driver.get(movie_url)
            
            # --- NOUVEAU : On scrolle un peu pour déclencher le lazy-loading ---
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(2)

            # Extraction des scores
            try:
                # On attend que l'un des conteneurs de score apparaisse
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "score-board, rt-score-card, [data-qa='score-panel'], [slot='critics-score']")))
                
                # Script JS ultra-complet pour chercher partout
                scores = self.driver.execute_script("""
                    let res = { tomatometer: null, audience: null };
                    
                    // 1. Chercher dans les Web Components
                    const sb = document.querySelector('score-board, rt-score-card');
                    if (sb) {
                        res.tomatometer = sb.getAttribute('tomatometerscore') || sb.getAttribute('critics-score');
                        res.audience = sb.getAttribute('audiencescore') || sb.getAttribute('audience-score') || sb.getAttribute('audience-average-rating');
                    }
                    
                    // 2. Chercher par data-qa
                    if (!res.tomatometer) res.tomatometer = document.querySelector('[data-qa="critics-score"]')?.innerText;
                    if (!res.audience) res.audience = document.querySelector('[data-qa="audience-score"]')?.innerText;
                    
                    // 3. Chercher dans les nouveaux éléments rt-text/rt-link
                    if (!res.audience) {
                        const audLink = document.querySelector('rt-link[slot="audience-reviews"] rt-text');
                        if (audLink) res.audience = audLink.innerText;
                    }

                    // 4. Chercher dans le JSON-LD (Critics uniquement souvent)
                    if (!res.tomatometer) {
                        const ld = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                            .map(s => { try { return JSON.parse(s.innerText); } catch(e) { return {}; } })
                            .find(j => j.aggregateRating);
                        if (ld) res.tomatometer = ld.aggregateRating.ratingValue;
                    }
                    
                    return res;
                """)
                
                if scores:
                    def clean(s):
                        if not s: return None
                        s = str(s).replace('%', '').replace('(', '').replace(')', '').strip()
                        return int(s) if s.isdigit() else None

                    movie.rt_tomatometer_score = clean(scores['tomatometer'])
                    movie.rt_audience_score = clean(scores['audience'])
                    
                    # --- NOUVEAU FALLBACK ULTIME : Regex sur le HTML Brut ---
                    if movie.rt_audience_score is None:
                        raw_html = self.driver.page_source
                        import re
                        # On cherche littéralement dans le code source HTML toutes les variantes d'attributs
                        patterns = [
                            r'audiencescore="(\d+)"',
                            r'audience-score="(\d+)"',
                            r'audience-average-rating="(\d+)"',
                            r'ratingscore="(\d+)"[^>]*>Audience',
                            r'slot="audience-score"[^>]*>\s*(\d+)\s*%',
                            r'class="percentage"[^>]*>(\d+)\s*%\s*</[^>]+>\s*<span[^>]*>\s*Audience',
                            r'Audience Score.*?(\d{1,3})%' # Recherche classique
                        ]
                        
                        for p in patterns:
                            m = re.search(p, raw_html, re.IGNORECASE | re.DOTALL)
                            if m:
                                movie.rt_audience_score = int(m.group(1))
                                print(f"   🕵️‍♂️ Audience Score trouvé via Regex (motif: {p})")
                                break

            except Exception as e:
                print(f"   ⚠️ Échec de l'extraction des scores : {e}")
            
            # Consensus
            try:
                consensus_elem = self.driver.find_element(By.CSS_SELECTOR, 'p[data-qa="critics-consensus"]')
                movie.rt_critics_consensus = consensus_elem.text
            except Exception:
                movie.rt_critics_consensus = None

            print(f"   ✅ RT Score: {movie.rt_tomatometer_score}% | Audience: {movie.rt_audience_score}%")
            
        except Exception as e:
            print(f"⚠️ Erreur globale pour {movie.title}: {e}")
        
        return movie

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    # --- TEST : MODE VISIBLE ---
    scraper = RTScraper(headless=False) 
    
    # Pour le test local, on importe datetime
    from datetime import datetime
    
    test_movie = Movie(
        tmdb_id=0,
        title="The Exorcist",
        release_date=datetime.strptime("1973-12-26", "%Y-%m-%d").date()
    )
    
    enriched_movie = scraper.search_and_enrich(test_movie)
    print(f"\nRésultat final : {enriched_movie}")
    
    time.sleep(2)
    scraper.close()