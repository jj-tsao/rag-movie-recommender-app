from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
from typing import List


class MovieRetriever:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str,
        popularity_weight: float = 0.4,  # Weight for popularity score boost during reranking
        rating_weight: float = 0.6,  # Weight for rating score boost during reranking
        retrieval_limit: int = 300,  # Number of movies to retrieve for reranking
        top_k: int = 20,  # Number of post-reranking movies to send to LLM
    ):
        self.client = qdrant_client
        self.collection_name = collection_name
        self.popularity_weight = popularity_weight
        self.rating_weight = rating_weight
        self.retrieval_limit = retrieval_limit
        self.top_k = top_k

    def embed(self, query: str, embed_fn) -> List[float]:
        return embed_fn(query)

    def retrieve_and_rerank(self, query_vector: List[float], genres=None, providers=None, year_range=None) -> List[dict]:
        # Construct Qdrant filter based on user input
        must_clauses = []

        if genres:
            genre_conditions = [FieldCondition(key="genres", match=MatchValue(value=genre)) for genre in genres]
            must_clauses.append({"should": genre_conditions})

        if providers:
            provider_conditions = [FieldCondition(key="watch_providers", match=MatchValue(value=provider)) for provider in providers]
            must_clauses.append({"should": provider_conditions})

        if year_range:
            must_clauses.append(
                FieldCondition(
                key="release_year",
                range=Range(gte=year_range[0], lte=year_range[1])
                )
            )

        qdrant_filter = Filter(must=must_clauses) if must_clauses else None

        # Initial retrieval from Qdrant
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=self.retrieval_limit,  # Number of movies for reranking
            with_payload=True,
            with_vectors=False,
        )

        if not hits:
            return []
        
        # Rerank initial results and return top_k movies
        reranked = self.rerank(hits)
        return reranked[:self.top_k]


    def rerank(self, hits) -> List[dict]:
        scored_docs = []
        
        payloads = [point.payload for point in hits.points]

        max_popularity = max((float(payload.get("popularity", 0)) for payload in payloads), default=800)

        # Construct reranking scores with popularity and rating
        for payload in payloads:
            popularity = float(payload.get("popularity", 0))
            vote_average = float(payload.get("vote_average", 0))

            norm_pop = popularity / max_popularity if max_popularity else 0
            norm_rating = vote_average / 10

            combined_score = (
                self.popularity_weight * norm_pop +
                self.rating_weight * norm_rating
            )

            scored_docs.append((payload, combined_score))

        # Rerank by combined score and return results
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [payload for payload, _ in scored_docs]
    
    
    def format_context(self, movies: list[dict]) -> str:  # Formart the retrieved content for LLM consumption
        return "\n\n".join([
            f"  {movie.get('content', '')}"
            for movie in movies
        ])