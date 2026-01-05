from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

from redis.asyncio import Redis  # injected client type

from reelix_core.types import MediaType


@dataclass
class CachedWhy:
    """
    Cached explanation for a (user, media_type, media_id) triple.
    """

    why_md: str
    imdb_rating: float | None = None
    rt_rating: float | None = None
    created_at: float = 0.0
    taste_version: str | None = None


class WhyCache:
    """
    Redis-backed why cache. One key per (user, media_type, media_id).
    Key:   {namespace}{user_id}:{media_type}:{media_id}
    Value: JSON string of CachedWhy fields.
    """

    def __init__(
        self,
        *,
        client: Redis,
        namespace: str = "reelix:why:",
        absolute_ttl_sec: int = 14 * 24 * 3600,
    ) -> None:
        # IMPORTANT: client should be created with decode_responses=True
        # so get() returns str (JSON) rather than bytes.
        self._r = client
        self._ns = namespace
        self._default_ttl = int(absolute_ttl_sec)

    def _key(self, user_id: str, media_type: MediaType, media_id: int) -> str:
        return f"{self._ns}{user_id}:{media_type.value}:{media_id}"

    def _serialize(self, value: CachedWhy) -> str:
        payload = {
            "why_md": value.why_md,
            "imdb_rating": value.imdb_rating,
            "rt_rating": value.rt_rating,
            "created_at": value.created_at,
            "taste_version": value.taste_version,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _deserialize(self, s: str | None) -> CachedWhy | None:
        if not s:
            return None
        try:
            data = json.loads(s)
        except Exception:
            return None
        why_md = data.get("why_md")
        if not isinstance(why_md, str):
            return None
        return CachedWhy(
            why_md=why_md,
            imdb_rating=data.get("imdb_rating"),
            rt_rating=data.get("rt_rating"),
            created_at=float(data.get("created_at") or 0.0),
            taste_version=data.get("taste_version"),
        )

    async def get_many(
        self,
        *,
        user_id: str,
        media_type: MediaType,
        media_ids: List[int],
    ) -> Dict[int, CachedWhy]:
        if not media_ids:
            return {}
        keys = [self._key(user_id, media_type, mid) for mid in media_ids]
        pipe = self._r.pipeline()
        for k in keys:
            pipe.get(k)
        results = await pipe.execute()
        out: Dict[int, CachedWhy] = {}
        for mid, raw in zip(media_ids, results):
            value = self._deserialize(raw)
            if value is not None:
                out[mid] = value
        return out

    async def set_many(
        self,
        *,
        user_id: str,
        media_type: MediaType,
        values: Dict[int, CachedWhy],
        ttl_sec: int | None = None,
    ) -> None:
        if not values:
            return
        ttl = int(ttl_sec or self._default_ttl)
        pipe = self._r.pipeline()
        for mid, value in values.items():
            k = self._key(user_id, media_type, mid)
            v = self._serialize(value)
            pipe.set(k, v, ex=ttl)
        await pipe.execute()

    async def get_one(
        self,
        *,
        user_id: str,
        media_type: MediaType,
        media_id: int,
    ) -> CachedWhy | None:
        res = await self.get_many(
            user_id=user_id,
            media_type=media_type,
            media_ids=[media_id],
        )
        return res.get(media_id)

    async def set_one(
        self,
        *,
        user_id: str,
        media_type: MediaType,
        media_id: int,
        value: CachedWhy,
        ttl_sec: int | None = None,
    ) -> None:
        await self.set_many(
            user_id=user_id,
            media_type=media_type,
            values={media_id: value},
            ttl_sec=ttl_sec,
        )

    async def aclose(self) -> None:
        # If you're sharing a single Redis client app-wide,
        # you may choose NOT to call this here.
        try:
            await self._r.aclose()
        except Exception:
            pass
