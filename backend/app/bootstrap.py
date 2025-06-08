import os
from pathlib import Path

import joblib
import nltk
from app.chatbot import build_chat_fn
from app.config import (
    BM25_PATH,
    INTENT_MODEL,
    NLTK_PATH,
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
)
from app.llm_services import load_sentence_model
from app.retriever import get_media_retriever
from app.vectorstore import connect_qdrant
from rank_bm25 import BM25Okapi
from transformers import pipeline

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def load_bm25_files() -> tuple[dict[str, BM25Okapi], dict[str, int]]:
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
    return bm25_models, bm25_vocabs


def setup_retriever():
    embed_model = load_sentence_model()
    qdrant_client = connect_qdrant(endpoint=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)
    nltk.data.path.append(str(NLTK_PATH))
    print("✅ NLTK resources loaded")

    bm25_models, bm25_vocabs = load_bm25_files()
    print("✅ BM25 files loaded")

    return get_media_retriever(
        embed_model=embed_model,
        qdrant_client=qdrant_client,
        bm25_models=bm25_models,
        bm25_vocabs=bm25_vocabs,
        movie_collection_name=QDRANT_MOVIE_COLLECTION_NAME,
        tv_collection_name=QDRANT_TV_COLLECTION_NAME,
    )


def setup_intent_classifier():
    print(f"🔧 Loading intent classifier from {INTENT_MODEL}")
    classifier = pipeline("text-classification", model=INTENT_MODEL)

    print("🔥 Warming up intent classifier...")
    warmup_queries = [
        "Can you recommend a feel-good movie?",
        "Who directed The Godfather?",
        "Do you like action films?",
    ]
    for q in warmup_queries:
        _ = classifier(q)

    print("🤖 Classifier ready")
    return classifier


# Initialize once at startup
retriever = setup_retriever()
intent_classifier = setup_intent_classifier()
chat_fn = build_chat_fn(retriever, intent_classifier)
