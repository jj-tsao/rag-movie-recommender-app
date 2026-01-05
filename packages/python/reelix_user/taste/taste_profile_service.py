from __future__ import annotations

from typing import Dict, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from reelix_core.types import BuildParams, MediaId, MediaType
from reelix_user_context.user_context_service import UserContextService
from reelix_user.taste.taste_builder_v2 import build_taste_vector

from .schemas import (
    TasteProfileMeta,
)
from .taste_profile_repo import SupabaseTasteProfileRepo
from .embedding_store import EmbeddingStore

EmbedMap = Mapping[MediaId, NDArray[np.float32]]


def load_vibe_centroids() -> Dict[str, np.ndarray]:
    return {}


def load_keyword_centroids() -> Dict[str, np.ndarray]:
    return {}


class TasteProfileService:
    def __init__(
        self,
        repo: SupabaseTasteProfileRepo,
        user_context: UserContextService,
        embeddings: EmbeddingStore,
    ):
        self.repo = repo
        self.user_context = user_context
        self.embeddings = embeddings

    # Existence / meta
    async def get_meta(
        self, user_id: str, media_type: MediaType
    ) -> TasteProfileMeta | None:
        return await self.repo.get_meta(user_id, media_type)

    # Rebuild & store
    async def rebuild(
        self,
        user_id: str,
        *,
        media_type: MediaType,
        params: BuildParams = BuildParams(dim=768),
    ) -> dict:
        signals = await self.user_context.fetch_user_signals(user_id, media_type)

        # Embedding fetcher from Qdrant for rated items (keep builder pure)
        def get_item_embeddings(ids: Sequence[MediaId]) -> EmbedMap:
            return self.embeddings.get_many(media_type, ids)

        vibe_centroids = load_vibe_centroids()
        keyword_centroids = load_keyword_centroids()

        vector, debug = build_taste_vector(
            user=signals,
            get_item_embeddings=get_item_embeddings,
            vibe_centroids=vibe_centroids,
            keyword_centroids=keyword_centroids,
            params=params,
        )
        await self.repo.upsert_taste_profile(user_id, media_type, vector, debug)

        # Return a small meta payload helpful to the client
        out = {
            "media_type": media_type,
            "positive_n": int(debug.get("pos_count", 0)),
            "negative_n": int(debug.get("neg_count", 0)),
            "params": debug.get("params"),
        }
        return out
