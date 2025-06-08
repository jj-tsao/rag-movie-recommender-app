from collections import Counter
from typing import Dict, List

from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range, models
from sentence_transformers import SentenceTransformer


class MediaRetriever:
    def __init__(
        self,
        embed_model: SentenceTransformer,
        qdrant_client: QdrantClient,
        bm25_models: Dict,
        bm25_vocabs: Dict,
        movie_collection_name: str,
        tv_collection_name: str,
        dense_weight: float = 0.4,  # Weight of semantic match score for reranking
        sparse_weight: float = 0.1,  # Weight of BM25 match score for reranking
        rating_weight: float = 0.3,  # Weight of rating score for reranking
        popularity_weight: float = 0.2,  # Weight of popularity score for reranking
        semantic_retrieval_limit: int = 300,  # Number of movies to retrieve for reranking
        bm25_retrieval_limit: int = 20,
        top_k: int = 20,  # Number of post-reranking movies to send to LLM
    ):
        self.client = qdrant_client
        self.movie_collection_name = movie_collection_name
        self.tv_collection_name = tv_collection_name
        self.embed_model = embed_model
        self.bm25_models = bm25_models
        self.bm25_vocabs = bm25_vocabs
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rating_weight = rating_weight
        self.popularity_weight = popularity_weight
        self.semantic_retrieval_limit = semantic_retrieval_limit
        self.bm25_retrieval_limit = bm25_retrieval_limit
        self.top_k = top_k

    def embed_dense(self, query: str) -> List[float]:
        return self.embed_model.encode(query).tolist()

    @staticmethod
    def tokenize_and_preprocess(text: str) -> List[str]:
        stop_words = set(stopwords.words("english"))
        stemmer = PorterStemmer()

        tokens = word_tokenize(text.lower())
        filtered_tokens = [w for w in tokens if w not in stop_words and w.isalnum()]
        processed_tokens = [stemmer.stem(w) for w in filtered_tokens]

        return processed_tokens

    def embed_sparse(self, query: str, media_type: str) -> Dict:
        bm25_model = (
            self.bm25_models["movie"]
            if media_type.lower() == "movies"
            else self.bm25_models["tv"]
        )
        bm25_vocab = (
            self.bm25_vocabs["movie"]
            if media_type.lower() == "movies"
            else self.bm25_vocabs["tv"]
        )

        tokens = self.tokenize_and_preprocess(query)

        term_counts = Counter(tokens)
        indices, values = [], []

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
        sparse_vector = {"indices": indices, "values": values}
        return sparse_vector

    def retrieve_and_rerank(
        self,
        dense_vector: List[float],
        sparse_vector: Dict,
        media_type: str = "movies",
        genres=None,
        providers=None,
        year_range=None,
    ) -> List[dict]:
        # Construct Qdrant filter based on user input
        qdrant_filter = self._build_filter(genres, providers, year_range)

        # Query Qdrant for semantic search with dense vector
        dense_results = self._query_dense(
            vector=dense_vector,
            media_type=media_type,
            qdrant_filter=qdrant_filter,
        )

        # Query Qdrant for BM25 search with sparse vector
        sparse_results = self._query_sparse(
            vector=sparse_vector,
            media_type=media_type,
            qdrant_filter=qdrant_filter,
        )

        if not dense_results:
            return []

        # Fuse dense and sparse results and rerank
        fused = self.fuse_dense_sparse(dense_results, sparse_results)
        reranked = self.rerank_fused_results(fused)

        reranked_ids = [p.id for p in reranked[:20]]
        print ("\nReranked Top-30:")
        for i, id_ in enumerate(reranked_ids):
            f = fused[id_]
            p = f["point"]
            print(
                f"#{i + 1} {p.payload.get('title', '')} | Score: {p.score} Dense: {f['dense_score']:.3f}, Sparse: {f['sparse_score']:.3f}, Pop: {p.payload.get('popularity', 0)}, Rating: {p.payload.get('vote_average', 0)}"
            )

        return reranked[: self.top_k]

    def _build_filter(
        self, genres=None, providers=None, year_range=None
    ) -> Filter | None:
        must_clauses = []

        if genres:
            genre_conditions = [
                FieldCondition(key="genres", match=MatchValue(value=genre))
                for genre in genres
            ]
            must_clauses.append({"should": genre_conditions})

        if providers:
            provider_conditions = [
                FieldCondition(key="watch_providers", match=MatchValue(value=provider))
                for provider in providers
            ]
            must_clauses.append({"should": provider_conditions})

        if year_range:
            must_clauses.append(
                FieldCondition(
                    key="release_year",
                    range=Range(gte=year_range[0], lte=year_range[1]),
                )
            )

        return Filter(must=must_clauses) if must_clauses else None

    def _query_dense(self, vector, media_type, qdrant_filter):
        collection = (
            self.movie_collection_name
            if media_type == "movies"
            else self.tv_collection_name
        )
        return self.client.query_points(
            collection_name=collection,
            query=vector,
            using="dense_vector",
            query_filter=qdrant_filter,
            limit=self.semantic_retrieval_limit,
            with_payload=["llm_context", "title", "popularity", "vote_average"],
            with_vectors=False,
        )

    def _query_sparse(self, vector, media_type, qdrant_filter):
        collection = (
            self.movie_collection_name
            if media_type == "movies"
            else self.tv_collection_name
        )
        return self.client.query_points(
            collection_name=collection,
            query=models.SparseVector(**vector),
            using="sparse_vector",
            query_filter=qdrant_filter,
            limit=self.bm25_retrieval_limit,
            with_payload=["llm_context", "title", "popularity", "vote_average"],
            with_vectors=False,
        )

    def fuse_dense_sparse(
        self,
        dense_results: List,
        sparse_results: List,
    ) -> Dict[str, Dict]:
        fused = {}

        # Add dense results
        for point in dense_results.points:
            fused[point.id] = {
                "point": point,
                "dense_score": point.score or 0.0,
                "sparse_score": 0.0,
            }

        max_sparse_score = max((pt.score for pt in sparse_results.points), default=1e-6)

        # Add sparse scores
        for point in sparse_results.points:
            if point.id in fused:
                fused[point.id]["sparse_score"] = (
                    min(point.score / max_sparse_score, 0.8) or 0.0
                )
            else:
                fused[point.id] = {
                    "point": point,
                    "dense_score": 0.0,
                    "sparse_score": min(point.score / max_sparse_score, 0.8) or 0.0,
                }

        return fused

    def rerank_fused_results(
        self,
        fused: Dict[str, Dict],
    ) -> List:
        max_popularity = max(
            (float(f["point"].payload.get("popularity", 0)) for f in fused.values()),
            default=1.0,
        )

        def compute_score(f):
            point = f["point"]
            dense_score = f["dense_score"]
            sparse_score = f["sparse_score"]
            popularity = float(point.payload.get("popularity", 0)) / max_popularity
            vote_average = float(point.payload.get("vote_average", 0)) / 10.0

            return (
                self.dense_weight * dense_score
                + self.sparse_weight * sparse_score
                + self.rating_weight * vote_average
                + self.popularity_weight * popularity
            )

        reranked = sorted(fused.values(), key=compute_score, reverse=True)

        return [f["point"] for f in reranked]

    def format_context(self, movies: list[dict]) -> str:
        # Formart the retrieved documents as context for LLM
        return "\n\n".join(
            [f"  {movie.payload.get('llm_context', '')}" for movie in movies]
        )


