import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

QDRANT_ENDPOINT = os.getenv("QDRANT_ENDPOINT")
QDRANT_MOVIE_COLLECTION_NAME = "Movies_BGE_AUG-RE"
QDRANT_TV_COLLECTION_NAME = "TV_Shows_BGE_AUG-RE"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

NLTK_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nltk_data"
BM25_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bm25_files"

INTENT_MODEL = "JJTsao/intent-classifier-distilbert-movierec"  # Fine-tuned intent classification model for query intent classifiation
EMBEDDING_MODEL = "JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5"  # Fine-tuned sentence transfomer model for query dense vector embedding
RERANKER_MODEL = "JJTsao/movietv-reranker-cross-encoder-base-v1"
OPENAI_MODEL = "gpt-4o-mini"  # LLM for chat completions


if not OPENAI_API_KEY or not QDRANT_API_KEY or not SUPABASE_API_KEY:
    raise ValueError("Missing API key(s).")
if (
    not QDRANT_ENDPOINT
    or not QDRANT_MOVIE_COLLECTION_NAME
    or not QDRANT_TV_COLLECTION_NAME
):
    raise ValueError("Missing QDrant URL or collection name.")
