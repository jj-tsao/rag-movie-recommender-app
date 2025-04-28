from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
from typing import List


class MovieRetriever:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        movie_collection_name: str,
        tv_collection_name: str,
        semantic_weight: float = 0.4,  # Weight of semantic match score for reranking
        popularity_weight: float = 0.2,  # Weight of popularity score for reranking
        rating_weight: float = 0.4,  # Weight of rating score for reranking
        retrieval_limit: int = 300,  # Number of movies to retrieve for reranking
        top_k: int = 20,  # Number of post-reranking movies to send to LLM
    ):
        self.client = qdrant_client
        self.movie_collection_name = movie_collection_name
        self.tv_collection_name = tv_collection_name
        self.semantic_weight = semantic_weight
        self.popularity_weight = popularity_weight
        self.rating_weight = rating_weight
        self.retrieval_limit = retrieval_limit
        self.top_k = top_k

    def embed(self, query: str, embed_fn) -> List[float]:
        return embed_fn(query)

    def retrieve_and_rerank(self, query_vector: List[float], media_type="movies", genres=None, providers=None, year_range=None) -> List[dict]:
        # Construct Qdrant filter based on user input
        must_clauses = []

        if genres:
            genre_conditions = [FieldCondition(key="genres", match=MatchValue(value=genre)) for genre in genres]
            must_clauses.append({"should": genre_conditions})

        if providers:
            provider_conditions = [FieldCondition(key="watch_providers", match=MatchValue(value=provider)) for provider in providers]
            must_clauses.append({"should": provider_conditions})

        must_clauses.append(
            FieldCondition(
            key="release_year",
            range=Range(gte=year_range[0], lte=year_range[1])
            )
        )

        qdrant_filter = Filter(must=must_clauses) if must_clauses else None

        # Initial retrieval from Qdrant
        hits = self.client.query_points(
            collection_name=self.movie_collection_name if media_type == "movies" else self.tv_collection_name,  # Qdrant collection name for moives or tv shows
            query=query_vector,
            query_filter=qdrant_filter,
            limit=self.retrieval_limit,  # Number of movies for reranking
            with_payload=["content", "title", "popularity", "vote_average"],
            with_vectors=False,
        )

        if not hits:
            return []
        
        # Rerank initial results and return top_k movies
        reranked = self.rerank(hits)
        return reranked[:self.top_k]


    def rerank(self, hits) -> List[dict]:
        scored_docs = []
        
        points = [point for point in hits.points]
        max_popularity = max((float(point.payload.get("popularity", 0)) for point in points), default=800)

        scored_docs = [(
            point.payload,
            (self.semantic_weight * point.score +
            self.popularity_weight * (float(point.payload.get("popularity", 0)) / max_popularity) +
            self.rating_weight * (float(point.payload.get("vote_average", 0)) / 10))
        ) for point in points]

        # Rerank by combined score and return results
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [payload for payload, _ in scored_docs]
    
    
    def format_context(self, movies: list[dict]) -> str: 
        # Formart the retrieved content as context for LLM
        return "\n\n".join([
            f"  {movie.get('content', '')}"
            for movie in movies
        ])
