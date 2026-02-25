from __future__ import annotations
from typing import Dict, List, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from reelix_retrieval.bm25_tokenizer import tokenize_for_bm25


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

    def encode_sparse(self, text: str, media_type: str) -> Dict[str, List[float]]:
        bm25_model = self.bm25_models[media_type.lower()]
        bm25_vocab = self.bm25_vocabs[media_type.lower()]

        tokens = tokenize_for_bm25(text)
        if not tokens:
            return {"indices": [], "values": []}

        term_counts = Counter(tokens)
        # --- NEW: clip tf and compute a "query length" independent of repetition
        tf_clip = 3
        unique_len = len(term_counts)  # use unique terms for normalization
        avg_doc_length = bm25_model.avgdl
        k1 = bm25_model.k1
        b_query = 0.0  # disable length normalization for the query

        indices, values = [], []
        for term, raw_tf in term_counts.items():
            if term not in bm25_vocab:
                continue
            tf = min(raw_tf, tf_clip)
            idf = bm25_model.idf.get(term, 0.0)

            # denominator uses unique_len and b_query (0.0) so repeats don't over-penalize
            denom = tf + k1 * (1 - b_query + b_query * (unique_len / avg_doc_length))
            if denom <= 0:
                continue
            weight = idf * tf * (k1 + 1) / denom
            indices.append(bm25_vocab[term])
            values.append(float(weight))

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
