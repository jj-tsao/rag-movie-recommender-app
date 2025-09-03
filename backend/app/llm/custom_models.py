import time
from pathlib import Path

import joblib
import torch
from app.core.config import BM25_PATH, EMBEDDING_MODEL, INTENT_MODEL, RERANKER_MODEL
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from transformers import pipeline

# Global model config
_sentence_model = None  # Not loaded at import time


def load_sentence_model():
    global _sentence_model
    if _sentence_model is None:
        print("Loading embedding model...")
        _sentence_model = SentenceTransformer(
            EMBEDDING_MODEL, device="cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"Model '{EMBEDDING_MODEL}' loaded. Performing GPU warmup...")

        # Realistic multi-sentence warmup to trigger full CUDA graph
        warmup_sentences = [
            "A suspenseful thriller with deep character development and moral ambiguity.",
            "Coming-of-age story with emotional storytelling and strong ensemble performances.",
            "Mind-bending sci-fi with philosophical undertones and high concept ideas.",
            "Recommend me some comedies.",
        ]
        _ = _sentence_model.encode(warmup_sentences, show_progress_bar=False)
        time.sleep(0.5)
        _ = _sentence_model.encode(warmup_sentences, show_progress_bar=False)
        print("🚀 Embedding model fully warmed up.")

    return _sentence_model


def setup_intent_classifier():
    print(f"Loading intent classifier from {INTENT_MODEL}")
    classifier = pipeline("text-classification", model=INTENT_MODEL)

    print("Warming up intent classifier...")
    warmup_queries = [
        "Can you recommend a feel-good movie?",
        "Who directed The Godfather?",
        "Do you like action films?",
    ]
    for q in warmup_queries:
        _ = classifier(q)

    print("🤖 Classifier ready")
    return classifier


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
        print("✅ BM25 files loaded")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Missing BM25 files: {e}")
    return bm25_models, bm25_vocabs

def load_cross_encoder(
    model_name: str = RERANKER_MODEL,
    batch_size: int = 32,
    max_length: int = 512,
):
    global _ce_model
    try:
        _ce_model
    except NameError:
        _ce_model = None

    if _ce_model is None:
        import time
        from app.ranking.cross_encoder_reranker import CrossEncoderReranker

        t0 = time.time()
        # Favor shorter sequences and larger batches on GPU for latency
        is_cuda = torch.cuda.is_available()
        effective_max_len = 256 if is_cuda else max_length
        effective_batch = 48 if is_cuda else batch_size
        _ce_model = CrossEncoderReranker(
            model_name=model_name,
            batch_size=effective_batch,
            max_length=effective_max_len,
        )
        try:
            _ = _ce_model.score("warmup query", ["warmup doc"])
        except Exception as e:
            print("⚠️ CE warmup error (continuing):", e)
        print(f"✅ CrossEncoder loaded in {time.time() - t0:.2f}s")
    return _ce_model
