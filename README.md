# 🧟 HorRAGor BOT

**HorRAGor** is a specialized conversational agent dedicated to the horror universe (cinema, literature, video games). To avoid hallucinations and provide "gore-met" information, it relies on a hybrid, rich, and perfectly structured knowledge base.

## 🎯 Objectives
This project validates the **Bloc E1** competencies by developing a robust ingestion pipeline capable of collecting, cleaning, and merging data from 5 heterogeneous sources. This data foundation serves as the core for the future **RAG (Retrieval-Augmented Generation)** architecture.

## 🏗️ Architecture: Multimodal Ingestion Pipeline

### 🌐 Data Sources (Parallel Acquisition)
1.  **Web Scraping (Selenium)**: Extraction from **Rotten Tomatoes** for trends and scores.
2.  **External API**: Metadata from **TMDB** (The Movie Database).
3.  **Local Files (Polars)**: Fast processing of **Kaggle** CSV datasets (horror literature).
4.  **Database (SQLite)**: Extraction from **IMDB** datasets (filtered on Horror genre & Quality).
5.  **Big Data (PySpark)**: Large-scale processing of massive data files.

### 🧩 Fusion & Reconciliation (Master Data Management)
The consolidation follows a strict priority logic:
1.  **TMDB** (Master Source: Official IDs & Titles)
2.  **Rotten Tomatoes** (Enrichment: Critics & Audience scores)
3.  **Kaggle** (Enrichment: Literary details & Synopses)
4.  **IMDB** (Enrichment: Casting & Trivia)
5.  **Spark Data** (Enrichment: Large scale text analysis)

**Matching Logic:**
- Level 1: `tmdb_id`
- Level 2: `imdb_id`
- Level 3: **Fuzzy Matching** on `[Title + Year]` (Levenshtein distance).

### 🛠️ Technical Specifications
- **Normalization**: Date standardization (ISO 8601), score scaling, and text cleaning (UTF-8, HTML stripping).
- **Filtering**: Strict "Horror/Gore" genre enforcement.
- **Persistence**: **PostgreSQL** hosted on **Supabase**, interfaced with **SQLAlchemy ORM**.
- **Modeling**: Full documentation including MCD, MLD, and MPD (Merise methodology).

## 📂 Project Structure
```bash
GorRAGor_bot/
├── app/
│   ├── utils/            # Normalization & Cleaning utilities
│   ├── tmdb.py           # TMDB API ingestion
│   ├── rt_scraper.py     # Selenium scraper for Rotten Tomatoes
│   ├── kaggle_ingest.py  # Polars-based CSV ingestion
│   ├── imdb_extract.py   # SQLite extraction logic
│   ├── spark_processor.py # PySpark big data processing
│   ├── fusion_engine.py  # MDM & Reconciliation logic
│   ├── models.py         # SQLAlchemy ORM models
│   └── database.py       # Supabase/PostgreSQL connection
├── data/
│   ├── raw/             # Raw source files (Kaggle CSVs)
│   ├── processed/       # Mid-pipeline processed data
│   └── sqlite/          # IMDB SQLite database
├── docs/                # Merise Diagrams (MCD, MLD, MPD)
├── tests/               # Unit and integration tests
├── .env.example         # Template for environment variables
├── pyproject.toml       # Project dependencies
└── README.md            # You are here
```

## 🚀 Getting Started
1. Install dependencies using `uv` or `pip`:
   ```bash
   pip install -r requirements.txt # or uv sync
   ```
2. Configure your `.env` file based on `.env.example`.
3. Run the ingestion pipeline (Module by module).

---
*Created by Antigravity for Simplon.co - HorRAGor Bot Project*
