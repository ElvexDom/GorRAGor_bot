# HorRAGor BOT

**HorRAGor** est un agent conversationnel spécialisé dans l'univers de l'horreur (cinéma, littérature, jeux vidéo). Pour éviter les hallucinations, il s'appuie sur une base de connaissances hybride construite à partir de 5 sources hétérogènes.

> Projet de validation **Bloc E1** — Simplon.co | Formateur : Antony Schutz

---

## Objectifs

Développer un pipeline d'ingestion capable de **collecter, nettoyer et fusionner** des données provenant de 5 sources hétérogènes. Ce socle sert de base à la future architecture **RAG (Retrieval-Augmented Generation)**.

---

## Pipeline d'ingestion (5 sources)

| Étape | Source | Technologie | Données collectées |
|---|---|---|---|
| 0 — Source maîtresse | TMDB API | `requests` | `title`, `overview`, `release_date`, `vote_average`, `popularity`, `poster_path` |
| 1 — Enrichissement | Rotten Tomatoes | Selenium | `tomatometer_score`, `audience_score`, `critics_consensus` |
| 2 — Enrichissement | Kaggle CSV | Polars | `budget`, `revenue`, `synopsis`, `tagline`, `runtime` |
| 3 — Enrichissement | IMDB SQLite | `sqlite3` | `imdb_rating`, `num_votes` (≥ 1000), `director`, `actors` |
| 4 — Enrichissement | PySpark | PySpark | `spark_extracted_keywords` (analyse textuelle) |

---

## Stratégie de fusion MDM

La consolidation suit une logique de **priorité décroissante** (TMDB → RT → Kaggle → IMDB → Spark).

**Méthodes de réconciliation :**
- Niveau 1 : correspondance exacte sur `tmdb_id`
- Niveau 2 : correspondance exacte sur `imdb_id`
- Niveau 3 : fuzzy matching sur `[Titre + Année]` (distance de Levenshtein via `rapidfuzz`)

---

## Spécifications techniques

- **Dates** : normalisées ISO 8601 — si année seule, fixée au `YYYY-01-01`
- **Scores** : RT conservé en 0-100 (pourcentage), TMDB et IMDB en 0-10
- **Textes** : suppression HTML, normalisation des espaces, encodage UTF-8
- **Dédoublonnage** : unicité sur `tmdb_id` en base + dédoublonnage Kaggle sur `title + release_date`
- **Filtrage** : seul le genre Horreur/Gore est conservé (genre TMDB `id=27`, filtre `genres LIKE '%Horror%'` IMDB)
- **Persistance** : PostgreSQL hébergé sur **Supabase**, interfacé via **SQLAlchemy ORM** — fallback SQLite local si `SUPABASE_DB_URL` absent

---

## Structure du projet

```
GorRAGor_bot/
├── app/
│   ├── ingestion/              # Les 5 sources de données
│   │   ├── tmdb.py             # TMDB API (source maîtresse)
│   │   ├── rt_scraper.py       # Scraping Rotten Tomatoes (Selenium)
│   │   ├── kaggle_ingest.py    # Lecture CSV Kaggle (Polars)
│   │   ├── imdb_extractor.py   # Extraction IMDB SQLite
│   │   └── spark_processor.py  # Analyse textuelle PySpark
│   ├── utils/
│   │   └── normalizers.py      # clean_txt, normalize_date
│   ├── __main__.py             # Point d'entrée CLI (argparse)
│   ├── database.py             # Connexion SQLAlchemy (Supabase / SQLite)
│   ├── models.py               # Modèle ORM Movie
│   └── fusion_engine.py        # Orchestrateur + logique MDM
├── data/
│   ├── db/                     # Base principale SQLAlchemy
│   │   └── horror_movies.db    # Générée automatiquement au premier lancement
│   └── tmp/                    # Fichiers téléchargés (ignorés par git)
│       ├── kaggle.csv   # Dataset Kaggle (téléchargé automatiquement via --kaggle)
│       ├── imdb.db             # Base IMDB construite (téléchargée via --imdb)
│       └── imdb_tsv/           # TSV IMDB bruts mis en cache
├── docs/                       # Documentation Merise (MCD, MLD, MPD)
├── tests/                      # Tests unitaires et d'intégration
├── .env.example                # Template des variables d'environnement
├── pyproject.toml              # Dépendances du projet (uv)
└── README.md
```

---

## Installation

```bash
# Cloner le repo
git clone <url>
cd GorRAGor_bot

# Installer les dépendances avec uv
uv sync

# Configurer l'environnement
cp .env.example .env
# Renseigner les variables dans .env (voir tableau ci-dessous)
```

### Variables d'environnement requises

| Variable | Obligatoire | Description |
|---|---|---|
| `TMDB_TOKEN` | Oui | Bearer token TMDB API v4 |
| `KAGGLE_API_TOKEN` | Oui | Token API Kaggle — téléchargement automatique du CSV et de la base IMDB |
| `SUPABASE_DB_URL` | Non | URL PostgreSQL Supabase (`postgresql://...`) — SQLite local en fallback |

> Le token Kaggle s'obtient sur [kaggle.com](https://www.kaggle.com/settings/account) → **Settings → API → Create New Token**.

---

## Déploiement Supabase (production)

1. Créer un projet sur [supabase.com](https://supabase.com)
2. Aller dans **Project Settings → Database → Connection string → URI**
3. Copier l'URL et l'ajouter dans `.env` :
   ```
   SUPABASE_DB_URL=postgresql://postgres:motdepasse@db.xxxx.supabase.co:5432/postgres
   ```
4. Relancer le pipeline — les tables sont créées automatiquement par SQLAlchemy :
   ```bash
   uv run python -m app --tmdb
   ```

> En développement, si `SUPABASE_DB_URL` est absent, le pipeline utilise automatiquement SQLite local (`data/db/horror_movies.db`).

---

## Utilisation

Activer le venv une fois au démarrage du terminal :

```bash
.venv\Scripts\Activate.ps1
```

### Ordre recommandé

```bash
python -m app --tmdb    # Étape 1 — Source maîtresse (~30-60 min)
python -m app --kaggle  # Étape 2 — Kaggle (~2 min, auto-download)
python -m app --imdb    # Étape 3 — IMDB (~2-3h, build auto)
python -m app --spark   # Étape 4 — Spark (~10-15 min)
python -m app --rt      # Étape 5 — Rotten Tomatoes (optionnel, ~8h+)
```

### Tout en une commande

```bash
python -m app --all
```

---

## Prérequis données

- **Kaggle** : le fichier `kaggle.csv` est téléchargé **automatiquement** si absent.
  Prérequis : configurer les credentials Kaggle dans `~/.kaggle/kaggle.json`
  ([Account → API → Create New Token](https://www.kaggle.com/settings/account))
  Dataset : `evangower/horror-movies`
- **IMDB** : la base `imdb.db` est téléchargée **automatiquement** si absente.
  Prérequis : configurer les credentials Kaggle dans `~/.kaggle/kaggle.json`
  Source : kernel Kaggle `priy998/imdb-sqlite`
  La jointure `title_basics ↔ title_ratings` filtrée sur Horror + `numVotes ≥ 1000` est effectuée à l'initialisation.

---

## Documentation

Les diagrammes Merise (MCD, MLD, MPD) sont disponibles dans le dossier [`docs/`](docs/).

---

*Projet HorRAGor BOT — Simplon.co DEV IA*
