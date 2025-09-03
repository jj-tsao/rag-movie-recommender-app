from __future__ import annotations
from typing import Dict, List, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import threading
import re

from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


_stop_words_lock = threading.Lock()
# Cache stopwords/stemmer at import to avoid per-call overhead
try:
    _STOP_WORDS = set(stopwords.words("english"))
except Exception as _e:  # Fallback if NLTK data missing at import
    print("⚠️ Failed to preload NLTK stopwords:", _e)
    _STOP_WORDS = set()
_STEMMER = PorterStemmer()


class Encoder:
    def __init__(
        self,
        dense_model: SentenceTransformer,
        bm25_models: Dict[str, BM25Okapi],
        bm25_vocabs: Dict[str, Dict[str, int]],
        max_workers: int = 2,
    ):
        self.dense_model = dense_model
        self.bm25_models = bm25_models  # {"movie": BM25Okapi, "tv": BM25Okapi}
        self.bm25_vocabs = bm25_vocabs  # {"movie": {term: idx}, "tv": {...}}
        self.max_workers = max_workers

    # Dense encoder (custom SentenceTransformer)
    def encode_dense(self, text: str) -> List[float]:
        return self.dense_model.encode(text).tolist()

    # Sparse encoder (BM25)
    @staticmethod
    def _tokenize_and_preprocess(text: str) -> List[str]:
        # Fast regex tokenization to avoid heavy Punkt tokenizers
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        # Use cached stopwords and stemmer
        with _stop_words_lock:
            sw = _STOP_WORDS
        filtered_tokens = [w for w in tokens if w not in sw]
        processed_tokens = [_STEMMER.stem(w) for w in filtered_tokens]
        return processed_tokens

    def encode_sparse(self, text: str, media_type: str) -> Dict[str, List[float]]:
        bm25_model = self.bm25_models[media_type.lower()]
        bm25_vocab = self.bm25_vocabs[media_type.lower()]

        tokens = self._tokenize_and_preprocess(text)
        if not tokens:
            return {"indices": [], "values": []}

        term_counts = Counter(tokens)
        indices: List[int] = []
        values: List[float] = []

        avg_doc_length = bm25_model.avgdl
        k1, b = bm25_model.k1, bm25_model.b

        for term, tf in term_counts.items():
            if term in bm25_vocab:
                idx = bm25_vocab[term]
                idf = bm25_model.idf.get(term, 0)
                numerator = idf * tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * len(tokens) / avg_doc_length)
                if denominator != 0:
                    weight = numerator / denominator
                    indices.append(idx)
                    values.append(float(weight))

        # Sort for DB-friendly layout
        if indices:
            pairs = sorted(zip(indices, values), key=lambda x: x[0])
            indices, values = [p[0] for p in pairs], [p[1] for p in pairs]

        return {"indices": indices, "values": values}

    # Encode both async
    def dense_and_sparse(
        self, text: str, media_type: str, parallel: bool = True
    ) -> Tuple[List[float], Dict[str, List[float]]]:
        if not parallel:
            return self.encode_dense(text), self.encode_sparse(text, media_type)

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            f_dense = ex.submit(self.encode_dense, text)
            f_sparse = ex.submit(self.encode_sparse, text, media_type)
            return f_dense.result(), f_sparse.result()
