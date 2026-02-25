import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

QDRANT_ENDPOINT = os.getenv("QDRANT_ENDPOINT")

DATABASE_URL = os.getenv("DATABASE_URL")
IMDB_RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"

BM25_DIR = Path(__file__).resolve().parent.parent / "data" / "bm25_files"

media_param = {
    "movie": {
        "min_rating": 6.0,
        "min_vote_count": 100,
    },
    "tv": {
        "min_rating": 6.3,
        "min_vote_count": 12,
    },
}

def build_param(media_type: str) -> dict:
    if media_type not in media_param:
        raise ValueError(f"Invalid media_type: {media_type}")
    return {
        "rating": media_param[media_type]["min_rating"],
        "vote_count": media_param[media_type]["min_vote_count"],
    }

