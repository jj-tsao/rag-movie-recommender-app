import os
from pathlib import Path

import joblib
import nltk
from rank_bm25 import BM25Okapi
from src.config import (
    NLTK_PATH,
    BM25_PATH,
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
)
from src.llm_services import load_sentence_model
from src.media_retriever import MediaRetriever
from src.vectorstore import connect_qdrant

os.environ["TOKENIZERS_PARALLELISM"] = "false"

def check_nltk_resources():
    for resource in ["punkt", "stopwords"]:
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            nltk.download("punkt_tab")
            nltk.download("stopwords")
            

def load_bm25_files() -> tuple[BM25Okapi, dict[str, int]]:
    bm25_dir = Path(BM25_PATH)
    try:
        bm25_models = {
            "movie": joblib.load(bm25_dir / "movie_bm25_model.joblib"),
            "tv": joblib.load(bm25_dir / "tv_bm25_model.joblib"),
        }
        bm25_vocabs = {
            "movie": joblib.load(bm25_dir / "movie_bm25_vocab.joblib"),
            "tv": joblib.load(bm25_dir / "tv_bm25_vocab.joblib"),
        }
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Missing BM25 files: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load BM25 model or vocab: {e}")

    return bm25_models, bm25_vocabs


def setup_retriever() -> MediaRetriever:
    model = load_sentence_model()
    qdrant_client = connect_qdrant(endpoint=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)
    nltk.data.path.append(str(NLTK_PATH))
    print("✅ NLTK resources loaded")
    bm25_models, bm25_vocabs = load_bm25_files()
    print("✅ BM25 files loaded")

    return MediaRetriever(
        qdrant_client,
        movie_collection_name=QDRANT_MOVIE_COLLECTION_NAME,
        tv_collection_name=QDRANT_TV_COLLECTION_NAME,
        embed_model=model,
        bm25_models=bm25_models,
        bm25_vocabs=bm25_vocabs,
    )
