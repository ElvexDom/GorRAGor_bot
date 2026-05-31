from sqlalchemy import Column, Integer, String, Float, Text, Date, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from app.utils.normalizers import clean_txt, normalize_date

Base = declarative_base()


class TMDBMovie(Base):
    __tablename__ = "tmdb_movies"

    tmdb_id        = Column(Integer, primary_key=True, index=True)
    title          = Column(String(255), index=True, nullable=False)
    original_title = Column(String(255), nullable=True)
    release_date   = Column(Date, nullable=True)
    overview       = Column(Text, nullable=True)
    popularity     = Column(Float, nullable=True)
    vote_average   = Column(Float, nullable=True)
    vote_count     = Column(Integer, nullable=True)
    poster_path    = Column(String(255), nullable=True)
    backdrop_path  = Column(String(255), nullable=True)

    rt_score       = relationship("RTScore",      back_populates="movie", uselist=False)
    kaggle_data    = relationship("KaggleData",   back_populates="movie", uselist=False)
    imdb_data      = relationship("IMDBData",     back_populates="movie", uselist=False)
    spark_analysis = relationship("SparkAnalysis",back_populates="movie", uselist=False)

    def get_summary(self) -> str:
        """Génère le bloc de texte pour l'indexation RAG."""
        desc = (
            (self.kaggle_data.synopsis if self.kaggle_data else None)
            or self.overview
            or "N/A"
        )
        rt    = self.rt_score
        imdb  = self.imdb_data
        spark = self.spark_analysis
        return (
            f"Titre: {self.title}\n"
            f"Réalisateur: {imdb.director if imdb else 'Inconnu'}\n"
            f"Mots-clés: {spark.extracted_keywords if spark else 'N/A'}\n"
            f"Synopsis: {desc}\n"
            f"Scores: TMDB {self.vote_average}/10 "
            f"| RT {rt.tomatometer_score if rt else 'N/A'}% "
            f"| IMDB {imdb.imdb_rating if imdb else 'N/A'}/10"
        )


class RTScore(Base):
    __tablename__ = "rt_scores"

    tmdb_id           = Column(Integer, ForeignKey("tmdb_movies.tmdb_id"), primary_key=True)
    tomatometer_score = Column(Integer, nullable=True)
    audience_score    = Column(Integer, nullable=True)
    critics_consensus = Column(Text, nullable=True)

    movie = relationship("TMDBMovie", back_populates="rt_score")


class KaggleData(Base):
    __tablename__ = "kaggle_data"

    tmdb_id         = Column(Integer, ForeignKey("tmdb_movies.tmdb_id"), primary_key=True)
    synopsis        = Column(Text, nullable=True)
    literary_details= Column(Text, nullable=True)
    budget          = Column(Float, nullable=True)
    revenue         = Column(Float, nullable=True)

    movie = relationship("TMDBMovie", back_populates="kaggle_data")


class IMDBData(Base):
    __tablename__ = "imdb_data"

    tmdb_id     = Column(Integer, ForeignKey("tmdb_movies.tmdb_id"), primary_key=True)
    imdb_id     = Column(String(20), unique=True, index=True, nullable=True)
    imdb_rating = Column(Float, nullable=True)
    num_votes   = Column(Integer, nullable=True)
    director    = Column(String(255), nullable=True)
    actors      = Column(Text, nullable=True)

    movie = relationship("TMDBMovie", back_populates="imdb_data")


class SparkAnalysis(Base):
    __tablename__ = "spark_analysis"

    tmdb_id            = Column(Integer, ForeignKey("tmdb_movies.tmdb_id"), primary_key=True)
    extracted_keywords = Column(Text, nullable=True)
    analysis           = Column(JSON, nullable=True)

    movie = relationship("TMDBMovie", back_populates="spark_analysis")
