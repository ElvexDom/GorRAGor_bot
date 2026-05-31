# MPD — Modèle Physique de Données

> Méthodologie Merise | HorRAGor BOT Partie 1
> Dérivé du [MLD](MLD.md) — Cible : PostgreSQL (Supabase) / SQLite (local)

---

## Moteurs de base de données

| Environnement | Moteur | Configuration |
|---|---|---|
| Production | PostgreSQL (Supabase) | `SUPABASE_DB_URL` dans `.env` |
| Développement | SQLite | `data/db/horror_movies.db` (fallback automatique) |

---

## DDL — Création des tables

```sql
-- ================================================================
-- TABLE 1 : SOURCE MAÎTRESSE — TMDB
-- ================================================================
CREATE TABLE IF NOT EXISTS tmdb_movies (
    tmdb_id         INTEGER         PRIMARY KEY,
    title           VARCHAR(255)    NOT NULL,
    original_title  VARCHAR(255),
    release_date    DATE,
    overview        TEXT,
    popularity      FLOAT,
    vote_average    FLOAT           CHECK (vote_average BETWEEN 0 AND 10),
    vote_count      INTEGER         CHECK (vote_count >= 0),
    poster_path     VARCHAR(255),
    backdrop_path   VARCHAR(255)
);

-- ================================================================
-- TABLE 2 : ENRICHISSEMENT 1 — ROTTEN TOMATOES
-- ================================================================
CREATE TABLE IF NOT EXISTS rt_scores (
    tmdb_id             INTEGER     PRIMARY KEY
                                    REFERENCES tmdb_movies(tmdb_id)
                                    ON DELETE CASCADE,
    tomatometer_score   INTEGER     CHECK (tomatometer_score BETWEEN 0 AND 100),
    audience_score      INTEGER     CHECK (audience_score BETWEEN 0 AND 100),
    critics_consensus   TEXT
);

-- ================================================================
-- TABLE 3 : ENRICHISSEMENT 2 — KAGGLE
-- ================================================================
CREATE TABLE IF NOT EXISTS kaggle_data (
    tmdb_id         INTEGER     PRIMARY KEY
                                REFERENCES tmdb_movies(tmdb_id)
                                ON DELETE CASCADE,
    synopsis        TEXT,
    literary_details TEXT,
    budget          FLOAT       CHECK (budget >= 0),
    revenue         FLOAT       CHECK (revenue >= 0)
);

-- ================================================================
-- TABLE 4 : ENRICHISSEMENT 3 — IMDB
-- ================================================================
CREATE TABLE IF NOT EXISTS imdb_data (
    tmdb_id     INTEGER     PRIMARY KEY
                            REFERENCES tmdb_movies(tmdb_id)
                            ON DELETE CASCADE,
    imdb_id     VARCHAR(20) UNIQUE,
    imdb_rating FLOAT       CHECK (imdb_rating BETWEEN 0 AND 10),
    num_votes   INTEGER     CHECK (num_votes >= 1000),
    director    VARCHAR(255),
    actors      TEXT
);

-- ================================================================
-- TABLE 5 : ENRICHISSEMENT 4 — SPARK & NLP
-- ================================================================
CREATE TABLE IF NOT EXISTS spark_analysis (
    tmdb_id             INTEGER     PRIMARY KEY
                                    REFERENCES tmdb_movies(tmdb_id)
                                    ON DELETE CASCADE,
    extracted_keywords  TEXT,
    analysis            JSON
);
```

---

## Index

```sql
CREATE INDEX IF NOT EXISTS idx_tmdb_title   ON tmdb_movies(title);
CREATE INDEX IF NOT EXISTS idx_imdb_imdb_id ON imdb_data(imdb_id);
```

---

## Correspondance SQLAlchemy → SQL

| Modèle | Attribut | Type SQLAlchemy | PostgreSQL | SQLite |
|---|---|---|---|---|
| `TMDBMovie` | `tmdb_id` | `Integer` PK | `INTEGER` PK | `INTEGER` PK |
| `TMDBMovie` | `title` | `String(255)` NOT NULL | `VARCHAR(255)` NOT NULL | `TEXT` NOT NULL |
| `TMDBMovie` | `release_date` | `Date` | `DATE` | `TEXT` ISO 8601 |
| `TMDBMovie` | `vote_average` | `Float` | `DOUBLE PRECISION` | `REAL` |
| `RTScore` | `tomatometer_score` | `Integer` | `INTEGER` | `INTEGER` |
| `RTScore` | `critics_consensus` | `Text` | `TEXT` | `TEXT` |
| `KaggleData` | `budget` | `Float` | `DOUBLE PRECISION` | `REAL` |
| `KaggleData` | `revenue` | `Float` | `DOUBLE PRECISION` | `REAL` |
| `IMDBData` | `imdb_id` | `String(20)` UK | `VARCHAR(20)` UNIQUE | `TEXT` UNIQUE |
| `IMDBData` | `imdb_rating` | `Float` | `DOUBLE PRECISION` | `REAL` |
| `IMDBData` | `num_votes` | `Integer` | `INTEGER` | `INTEGER` |
| `SparkAnalysis` | `extracted_keywords` | `Text` | `TEXT` | `TEXT` |
| `SparkAnalysis` | `analysis` | `JSON` | `JSONB` | `TEXT` |

---

## Stratégie de persistance

### Upsert via `db.merge()`
SQLAlchemy utilise `Session.merge()` sur chaque objet :
- Si la PK existe → **mise à jour**
- Si la PK est absente → **insertion**

Le pipeline est ainsi **idempotent** : relancer `--tmdb` ou `--kaggle` ne crée pas de doublons.

### Commits par batch de 500
```python
if (i + 1) % 500 == 0:
    db.commit()
```

### Isolation par source
Chaque commande (`--rt`, `--kaggle`…) ne touche qu'à **sa propre table**. Une erreur sur l'enrichissement RT n'affecte pas `kaggle_data` ou `imdb_data`.

### Suppression en cascade
`ON DELETE CASCADE` sur toutes les FK : supprimer un film de `tmdb_movies` supprime automatiquement ses enrichissements dans les 4 autres tables.

---

## Justification du modèle physique

Le MPD conserve les **5 tables distinctes** issues du MLD sans dénormalisation. Ce choix est justifié par :

- **Absence de redondance** : aucune donnée n'apparaît dans deux tables à la fois — `imdb_id` est exclusivement dans `imdb_data` (donnée IMDB), `tmdb_movies` ne contient que des données TMDB
- **Intégrité référentielle** : les FK avec `ON DELETE CASCADE` garantissent la cohérence entre la source maîtresse et ses enrichissements
- **Maintenabilité** : chaque étape du pipeline écrit dans une table isolée — une modification de source n'impacte pas les autres
- **Requêtes RAG** : SQLAlchemy charge les relations via `lazy loading` — `movie.rt_score`, `movie.kaggle_data` etc. sont accessibles sans JOIN manuel
- **Conformité RGPD** : minimisation des données (seules les données utiles au RAG sont stockées), données publiques uniquement, aucune donnée personnelle des utilisateurs

---

## Conformité RGPD

| Principe | Application |
|---|---|
| Minimisation des données | Seules les colonnes utiles au RAG sont présentes dans chaque table |
| Données publiques uniquement | TMDB, RT, Kaggle, IMDB sont des sources publiques sur des œuvres culturelles |
| Pas de données personnelles | Aucun email, mot de passe ou donnée utilisateur dans le schéma |
| Traçabilité par source | Chaque donnée est isolée dans la table de sa source d'origine |
