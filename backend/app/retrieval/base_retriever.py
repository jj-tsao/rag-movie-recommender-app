from __future__ import annotations
from typing import Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter as QFilter, models as qmodels
from app.ranking.types import Candidate

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
        return self.movie_collection if media_type.lower() == "movie" else self.tv_collection

    def dense(
        self,
        dense_vec: List[float],
        media_type: str,
        qfilter: Optional[QFilter] = None,
        limit: int = 300,
    ) -> List[Candidate]:
        res = self.client.search(
            collection_name=self._col(media_type),
            query_vector=qmodels.NamedVector(name=self.dense_name, vector=dense_vec),
            limit=limit,
            with_payload=["llm_context", "embedding_text", "media_id", "title", "popularity", "vote_average"],
            query_filter=qfilter,
        )
        return [Candidate(id=p.id, payload=p.payload, dense_score=float(p.score)) for p in res]

    def sparse(
        self,
        sparse_vec: Dict[str, List[float]],
        media_type: str,
        qfilter: Optional[QFilter] = None,
        limit: int = 20,
    ) -> List[Candidate]:
        res = self.client.search(
            collection_name=self._col(media_type),
            query_vector=qmodels.NamedSparseVector(
                    name=self.sparse_name,
                    vector=qmodels.SparseVector(
                        indices=sparse_vec.get("indices", []),
                        values=[float(v) for v in sparse_vec.get("values", [])],
                    ),
                ),
            limit=limit,
            # Sparse phase does not need CE text; keep payload light
            with_payload=["llm_context", "media_id", "title", "popularity", "vote_average"],
            query_filter=qfilter,
        )
        return [Candidate(id=p.id, payload=p.payload, sparse_score=float(p.score)) for p in res]
