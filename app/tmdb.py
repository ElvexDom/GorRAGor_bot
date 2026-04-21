import requests
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

token = os.getenv("TMDB_TOKEN")

if not token:
    raise ValueError("TMDB_TOKEN manquant dans le fichier .env")

token = token.strip()

# Endpoint TMDB
url = "https://api.themoviedb.org/3/discover/movie"

headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {token}"
}

params = {
    "include_adult": "false",
    "include_video": "false",
    "language": "en-US",
    "page": 1,
    "sort_by": "popularity.desc"
}

# Requête API
response = requests.get(url, headers=headers, params=params)
response.raise_for_status()

data = response.json()

# Transformation des données
movies = []

for m in data.get("results", []):
    movies.append({
        "title": m.get("title"),
        "overview": m.get("overview"),
        "release_date": m.get("release_date"),
        "vote_average": m.get("vote_average"),
        "popularity": m.get("popularity"),
        "poster_url": f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}" if m.get("poster_path") else None
    })

# Affichage propre
for movie in movies:
    print(movie)