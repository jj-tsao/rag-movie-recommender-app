from __future__ import annotations
from typing import Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter as QFilter, models as qmodels
from reelix_ranking.types import Candidate


class BaseRetriever:
    def __init__(
        self,
        client: QdrantClient,
        *,
        movie_collection: str,
        tv_collection: str,
        dense_vector_name: str = "dense_vector",
        sparse_vector_name: str = "sparse_vector",
    ):
        self.client = client
        self.movie_collection = movie_collection
        self.tv_collection = tv_collection
        self.dense_name = dense_vector_name
        self.sparse_name = sparse_vector_name

    def _col(self, media_type: str) -> str:
        return (
            self.movie_collection
            if media_type.lower() == "movie"
            else self.tv_collection
        )

    def dense(
        self,
        dense_vec: List[float],
        media_type: str,
        qfilter: Optional[QFilter] = None,
        limit: int = 300,
    ) -> List[Candidate]:
        res = self.client.query_points(
            collection_name=self._col(media_type),
            query=dense_vec,
            using=self.dense_name,
            limit=limit,
            with_payload=[
                "llm_context",
                "embedding_text",
                "media_id",
                "title",
                "release_year",
                "genres",
                "poster_url",
                "backdrop_url",
                "trailer_key",
                "imdb_rating",
                "imdb_votes",
                "rt_score",
                "vote_average",
                "vote_count",
                "popularity",
                "release_date",
                "collection",
            ],
            query_filter=qfilter,
            with_vectors=False,
        )
        return [
            Candidate(id=int(p.id), payload=p.payload if p.payload is not None else {}, dense_score=float(p.score))
            for p in res.points
        ]

    def sparse(
        self,
        sparse_vec: Dict[str, List[float]],
        media_type: str,
        qfilter: Optional[QFilter] = None,
        limit: int = 20,
    ) -> List[Candidate]:
        sparse_query = qmodels.SparseVector(
            indices=[int(i) for i in sparse_vec.get("indices", [])],
            values=[float(v) for v in sparse_vec.get("values", [])],
        )

        res = self.client.query_points(
            collection_name=self._col(media_type),
            query=sparse_query,
            using=self.sparse_name,
            limit=limit,
            with_payload=[
                "llm_context",
                "embedding_text",
                "media_id",
                "title",
                "release_year",
                "genres",
                "poster_url",
                "backdrop_url",
                "trailer_key",
                "imdb_rating",
                "imdb_votes",
                "rt_score",
                "vote_average",
                "vote_count",
                "popularity",
                "release_date",
                "collection",
            ],
            query_filter=qfilter,
            with_vectors=False,
        )
        return [
            Candidate(id=int(p.id), payload=p.payload if p.payload is not None else {}, sparse_score=float(p.score))
            for p in res.points
        ]
