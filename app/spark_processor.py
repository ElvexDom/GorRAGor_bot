from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, regexp_replace, split, explode, count as spark_count
from typing import List
try:
    from app.models import Movie
except ImportError:
    from models import Movie


class SparkProcessor:
    def __init__(self, app_name: str = "HorRAGorSparkProcessor"):
        self.spark = SparkSession.builder \
            .appName(app_name) \
            .master("local[*]") \
            .getOrCreate()
        # Reduire les logs Spark
        self.spark.sparkContext.setLogLevel("WARN")
        print("SparkProcessor: SparkSession initialisee.")

    def process_overviews(self, movies: List[Movie]) -> List[Movie]:
        """
        Analyse les synopsis de tous les films pour extraire les mots-cles dominants.
        Enrichit chaque objet Movie avec 'spark_extracted_keywords'.
        """
        if not movies:
            return movies

        # Stopwords etendus (anglais)
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "with", "is", "was", "of", "from", "by", "are", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "shall", "can", "need", "dare",
            "ought", "used", "her", "his", "its", "their", "our", "your", "my",
            "this", "that", "these", "those", "who", "whom", "which", "what",
            "where", "when", "how", "not", "no", "nor", "as", "if", "then",
            "than", "too", "very", "just", "about", "above", "after", "again",
            "all", "also", "any", "because", "before", "between", "both",
            "each", "few", "more", "most", "other", "some", "such", "only",
            "own", "same", "so", "into", "over", "under", "until", "while",
            "she", "him", "they", "them", "them", "we", "you", "it", "he",
            "out", "up", "one", "two", "new", "now", "way", "even", "back",
            "there", "here", "every", "must", "through", "during", "being",
            "once", "upon", "find", "finds", "get", "gets", "goes", "come",
            "comes", "take", "takes", "make", "makes", "know", "life",
        }

        # 1. Conversion en DataFrame Spark
        data = [(m.tmdb_id, m.overview if m.overview else "") for m in movies]
        df = self.spark.createDataFrame(data, ["tmdb_id", "overview"])

        # 2. Nettoyage et tokenisation
        cleaned = df.withColumn(
            "clean_text",
            lower(regexp_replace(col("overview"), "[^a-zA-Z\\s]", ""))
        )

        # 3. Extraction de mots-cles par film
        # On utilise une approche par collecte puis traitement Python
        # (adapte pour des volumes moyens, Spark apporte la parallelisation)
        results = {}
        for row in cleaned.collect():
            tmdb_id = row.tmdb_id
            text = row.clean_text
            if not text:
                results[tmdb_id] = ""
                continue

            words = text.split()
            # Filtrage: mots > 3 lettres, pas des stopwords
            filtered = [w for w in words if len(w) > 3 and w not in stopwords]

            # Comptage de frequence
            freq = {}
            for w in filtered:
                freq[w] = freq.get(w, 0) + 1

            # Top 5 mots-cles
            top_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]
            results[tmdb_id] = ", ".join([kw for kw, _ in top_keywords])

        # 4. Mise a jour des objets Movie
        count = 0
        for m in movies:
            kw = results.get(m.tmdb_id, "")
            if kw:
                m.spark_extracted_keywords = kw
                count += 1

        print(f"Spark: {count} films analyses (mots-cles extraits).")
        return movies

    def close(self):
        if self.spark:
            self.spark.stop()
            print("SparkProcessor: SparkSession fermee.")


if __name__ == "__main__":
    processor = SparkProcessor()
    try:
        test_movies = [
            Movie(tmdb_id=1, title="Movie A",
                  overview="A scary movie about ghosts and haunted houses in the dark forest at midnight."),
            Movie(tmdb_id=2, title="Movie B",
                  overview="A bloody slasher where a masked killer chases teenagers through the abandoned woods.")
        ]
        processor.process_overviews(test_movies)
        for m in test_movies:
            print(f"Keywords pour {m.title}: {m.spark_extracted_keywords}")
    finally:
        processor.close()
