# MLD — Modèle Logique de Données

> Méthodologie Merise | HorRAGor BOT Partie 1
> Dérivé du [MCD](MCD.md)

---

## Règles de passage MCD → MLD appliquées

| Règle Merise | Application |
|---|---|
| Toute entité devient une table | 5 entités → 5 tables |
| Identifiant de l'entité → clé primaire | `tmdb_id` PK dans chaque table d'enrichissement |
| Association `(1,1)/(0,1)` → clé étrangère côté optionnel | `tmdb_id` FK dans les 4 tables d'enrichissement |
| Pas d'association `(n,n)` | Aucune table de jonction nécessaire |

---

## Schéma

```
tmdb_movies (tmdb_id, title, original_title, release_date,
             overview, popularity, vote_average, vote_count,
             poster_path, backdrop_path)
    PK  : tmdb_id


rt_scores (tmdb_id#, tomatometer_score, audience_score, critics_consensus)
    PK  : tmdb_id
    FK  : tmdb_id → tmdb_movies.tmdb_id


kaggle_data (tmdb_id#, synopsis, literary_details, budget, revenue)
    PK  : tmdb_id
    FK  : tmdb_id → tmdb_movies.tmdb_id


imdb_data (tmdb_id#, imdb_id*, imdb_rating, num_votes, director, actors)
    PK  : tmdb_id
    UK  : imdb_id
    FK  : tmdb_id → tmdb_movies.tmdb_id


spark_analysis (tmdb_id#, extracted_keywords, analysis)
    PK  : tmdb_id
    FK  : tmdb_id → tmdb_movies.tmdb_id
```

> `*` = unique nullable | `#` = clé étrangère

---

## Diagramme

```mermaid
erDiagram

    tmdb_movies {
        int     tmdb_id         PK
        string  title
        string  original_title
        date    release_date
        text    overview
        float   popularity
        float   vote_average
        int     vote_count
        string  poster_path
        string  backdrop_path
    }

    rt_scores {
        int     tmdb_id         PK_FK
        int     tomatometer_score
        int     audience_score
        text    critics_consensus
    }

    kaggle_data {
        int     tmdb_id         PK_FK
        text    synopsis
        text    literary_details
        float   budget
        float   revenue
    }

    imdb_data {
        int     tmdb_id         PK_FK
        string  imdb_id         UK
        float   imdb_rating
        int     num_votes
        string  director
        text    actors
    }

    spark_analysis {
        int     tmdb_id         PK_FK
        text    extracted_keywords
        json    analysis
    }

    tmdb_movies ||--o| rt_scores      : "tmdb_id"
    tmdb_movies ||--o| kaggle_data    : "tmdb_id"
    tmdb_movies ||--o| imdb_data      : "tmdb_id"
    tmdb_movies ||--o| spark_analysis : "tmdb_id"
```

---

## Contraintes d'intégrité

| Contrainte | Table | Colonne | Règle |
|---|---|---|---|
| PK | toutes | `tmdb_id` | Non null, unique |
| UK | `imdb_data` | `imdb_id` | Unique, nullable |
| NOT NULL | `tmdb_movies` | `title` | Tout film doit avoir un titre |
| FK + CASCADE | enrichissements | `tmdb_id` | Suppression film → suppression enrichissements |
| CHECK | `tmdb_movies` | `vote_average` | Entre 0 et 10 |
| CHECK | `rt_scores` | `tomatometer_score` | Entre 0 et 100 |
| CHECK | `rt_scores` | `audience_score` | Entre 0 et 100 |
| CHECK | `imdb_data` | `imdb_rating` | Entre 0 et 10 |
| CHECK | `imdb_data` | `num_votes` | >= 1000 |

---

## Justification du modèle

Le passage MCD → MLD donne naturellement **5 tables**, une par source de données. Ce choix est délibérément conservé (sans dénormalisation) pour les raisons suivantes :

- **Absence de redondance** : `imdb_id` apparaît uniquement dans `imdb_data` (donnée IMDB) — `tmdb_movies` ne contient que des données TMDB
- **Cohérence avec le pipeline** : chaque commande (`--tmdb`, `--rt`, `--kaggle`, `--imdb`, `--spark`) alimente exactement une table, sans effet de bord sur les autres
- **Conformité MDM** : la table `tmdb_movies` est la *source maîtresse*, les 4 autres sont des *enrichissements* — la structure reflète directement la stratégie de fusion décrite dans le PDF
- **Maintenabilité** : une source défaillante ou modifiée n'impose de toucher qu'à sa propre table
- **Performance RAG** : la méthode `get_summary()` construit le bloc d'indexation via les relations SQLAlchemy (`movie.rt_score`, `movie.kaggle_data`…) en une seule requête avec jointures automatiques
