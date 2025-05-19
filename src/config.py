import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # Automatically loads from `.env` in current working directory

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

QDRANT_ENDPOINT = os.getenv("QDRANT_ENDPOINT")
QDRANT_MOVIE_COLLECTION_NAME = os.getenv("QDRANT_MOVIE_COLLECTION_NAME_BGE")
QDRANT_TV_COLLECTION_NAME = os.getenv("QDRANT_TV_COLLECTION_NAME_BGE")

NLTK_PATH = Path(__file__).resolve().parent.parent / "data" / "nltk_data"
BM25_PATH = Path(__file__).resolve().parent.parent / "data" / "bm25_files"


if not OPENAI_API_KEY or not QDRANT_API_KEY:
    raise ValueError("Missing API key(s).")
if not QDRANT_ENDPOINT or not QDRANT_MOVIE_COLLECTION_NAME or not QDRANT_TV_COLLECTION_NAME:
    raise ValueError("Missing QDrant URL or collection name.")
