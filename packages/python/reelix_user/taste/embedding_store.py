from __future__ import annotations

from typing import Dict, Protocol, Sequence

import numpy as np
from numpy.typing import NDArray
from qdrant_client import QdrantClient
from reelix_core.types import MediaType, MediaId
from reelix_core.config import QDRANT_MOVIE_COLLECTION_NAME, QDRANT_TV_COLLECTION_NAME

EmbedMap = Dict[MediaId, NDArray[np.float32]]

class EmbeddingStore(Protocol):
    def get_many(self, media_type: MediaType, ids: Sequence[MediaId]) -> EmbedMap: ...

class QdrantEmbeddingStore:
    def __init__(self, client: QdrantClient, *, movie_collection=QDRANT_MOVIE_COLLECTION_NAME, tv_collection=QDRANT_TV_COLLECTION_NAME):
        self.client = client
        self.collections = {
            MediaType.MOVIE: movie_collection,
            MediaType.TV: tv_collection,
        }

    def get_many(self, media_type: MediaType, ids: Sequence[MediaId], vector_name: str = "dense_vector") -> EmbedMap:
        if not ids:
            return {}
        coll = self.collections[media_type]
        # Example: payload key "embedding" — change if yours differs
        points = self.client.retrieve(collection_name=coll, ids=list(ids), with_vectors=True)
        out: EmbedMap = {}
        for p in points:
            vec = p.vector.get(vector_name) if isinstance(p.vector, dict) else p.vector
            out[int(p.id)] = np.asarray(vec, dtype=np.float32)
        return out
