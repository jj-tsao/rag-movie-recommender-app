from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from anyio import to_thread
from reelix_core.config import EMBEDDING_MODEL
from reelix_core.types import MediaType

from .schemas import (
    TasteProfileMeta,
)

TABLE_TASTE = "user_taste_profile"
TABLE_INTERACTIONS = "user_interactions"


def _ensure_ts(value) -> datetime | None:
    """Normalize timestamps coming from Postgres/Supabase into tz-aware datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Supabase returns ISO strings that may end with `Z`; make them explicit UTC.
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


class SupabaseTasteProfileRepo:
    def __init__(self, client):
        self.client = client

    # ---------- Async facade ----------
    async def get_meta(
        self, user_id: str, media_type: MediaType
    ) -> Optional[TasteProfileMeta]:
        return await to_thread.run_sync(self._get_meta_sync, user_id, media_type)

    async def upsert_taste_profile(
        self,
        user_id: str,
        media_type: MediaType,
        vector: np.ndarray,
        debug: dict[str, Any],
        *,
        model_name: str = EMBEDDING_MODEL,
        dim: int = 768,
    ) -> None:
        await to_thread.run_sync(
            self._upsert_taste_profile_sync,
            user_id,
            media_type,
            vector,
            debug,
            model_name,
            dim,
        )

    # ---------- Private sync impls ----------
    def _get_meta_sync(
        self, user_id: str, media_type: MediaType
    ) -> Optional[TasteProfileMeta]:
        res = (
            self.client.table(TABLE_TASTE)
            .select("model_name, dim, positive_n, negative_n, last_built_at")
            .eq("user_id", user_id)
            .eq("media_type", media_type.value)
            .order("last_built_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        r = rows[0]
        return TasteProfileMeta(
            media_type=media_type,
            model_name=r.get("model_name"),
            dim=r.get("dim"),
            positive_n=r.get("positive_n"),
            negative_n=r.get("negative_n"),
            last_built_at=_ensure_ts(r.get("last_built_at")),
        )

    def _upsert_taste_profile_sync(
        self,
        user_id: str,
        media_type: MediaType,
        vector: np.ndarray,
        debug: dict[str, Any],
        model_name: str = EMBEDDING_MODEL,
        dim: int = 768,
    ) -> None:
        try:
            payload = {
                "user_id": user_id,
                "media_type": media_type.value,
                "dense": list(map(float, vector)),
                "model_name": model_name,
                "dim": dim or debug.get("dim"),
                "positive_n": int(debug.get("pos_count", 0)),
                "negative_n": int(debug.get("neg_count", 0)),
                "last_built_at": "now()",
                "params": debug,
            }
            self.client.table(TABLE_TASTE).upsert(payload).execute()
        except Exception as e:
            print(f"Unexpected DB error: {repr(e)}")
