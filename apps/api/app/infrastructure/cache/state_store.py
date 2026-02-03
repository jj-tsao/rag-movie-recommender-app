from __future__ import annotations

import gzip
import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError

JsonObj = dict[str, Any]


def _json_default(o: Any):
    # Pydantic v2
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    # Pydantic v1 fallback
    if hasattr(o, "dict"):
        return o.dict()
    # Enums
    if isinstance(o, Enum):
        return o.value
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


# Models
@dataclass
class SessionState:
    """Multi-turn session memory for the agent."""

    user_id: str
    summary: JsonObj | None = None
    last_spec: JsonObj | None = None
    slot_map: JsonObj | None = None
    seen_media_ids: list[int] | None = None
    created_at: float | None = None
    updated_at: float | None = None

    def to_orchestrator(self) -> JsonObj:
        return {
            "summary": self.summary,
            "last_spec": self.last_spec,
            "slot_map": self.slot_map,
            "seen_media_ids": self.seen_media_ids,
        }

# Store
class StateStore:
    """
    Redis agent state store for session memory: reelix:agent:session:{session_id}
    """

    def __init__(
        self,
        *,
        client: Redis,
        namespace: str = "reelix:agent:session:",
        absolute_ttl_sec: int = 7 * 24 * 3600,  # 7d cap
        compression_level: int = 5,
    ) -> None:
        self._r = client
        self._sns = namespace
        self._sess_cap = int(absolute_ttl_sec)
        self._level = int(compression_level)

    def _now(self) -> float:
        return time.time()

    # ----- codec -----

    def _encode(self, obj: JsonObj) -> bytes:
        raw = json.dumps(
            obj,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,  # defensive: handles Enums/Pydantic if any slip through
        ).encode("utf-8")
        return gzip.compress(raw, compresslevel=self._level)

    def _decode(self, b: bytes) -> JsonObj | None:
        try:
            raw = gzip.decompress(b)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    # ----- keys -----

    def _session_key(self, session_id: str) -> str:
        return f"{self._sns}{session_id}"

    # ----- helpers -----

    async def _touch(self, key: str, ttl_sec: int) -> None:
        try:
            await self._r.expire(key, int(ttl_sec))
        except (RedisError, RuntimeError):
            # Redis hiccup shouldn't fail a request.
            return

    async def _delete(self, key: str) -> None:
        try:
            await self._r.delete(key)
        except (RedisError, RuntimeError):
            return

    def _expired(self, created_at: float, cap_sec: int) -> bool:
        return bool(cap_sec and created_at and (self._now() - created_at) > cap_sec)

    # Sessions
    async def put_session(
        self, *, session_id: str, state: SessionState, ttl_sec: int
    ) -> None:
        now = self._now()
        if state.created_at is None:
            state.created_at = now
        state.updated_at = now

        payload = asdict(state)
        payload["__kind"] = "session"
        payload["__created_at"] = float(state.created_at or now)

        try:
            await self._r.set(
                self._session_key(session_id), self._encode(payload), ex=int(ttl_sec)
            )
        except (RedisError, RuntimeError):
            return

    async def get_session(
        self,
        *,
        session_id: str,
        touch: bool = True,
        ttl_sec: int | None = 24*3600,
    ) -> SessionState | None:
        key = self._session_key(session_id)
        try:
            b = await self._r.get(key)
        except (RedisError, RuntimeError):
            # Treat Redis connection errors as cache misses.
            return None
        if not b:
            return None

        payload = self._decode(b)
        if not payload:
            await self._delete(key)
            return None

        created_at = float(
            payload.get("__created_at") or payload.get("created_at") or 0.0
        )
        if created_at and self._expired(created_at, self._sess_cap):
            await self._delete(key)
            return None

        if touch and ttl_sec is not None:
            await self._touch(key, ttl_sec)

        return SessionState(
            user_id=str(payload.get("user_id", "")),
            summary=payload.get("summary"),
            last_spec=payload.get("last_spec"),
            slot_map=payload.get("slot_map"),
            seen_media_ids=payload.get("seen_media_ids"),
            created_at=float(payload.get("created_at") or created_at or 0.0) or None,
            updated_at=float(payload.get("updated_at") or 0.0) or None,
        )

    async def delete_session(self, *, session_id: str) -> None:
        await self._delete(self._session_key(session_id))

    async def update_session(
        self,
        *,
        session_id: str,
        ttl_sec: int,
        mutate: Callable[[JsonObj], None],
    ) -> bool:
        """Read-modify-write update (not atomic across processes)."""
        key = self._session_key(session_id)
        try:
            b = await self._r.get(key)
        except (RedisError, RuntimeError):
            return False
        if not b:
            return False

        payload = self._decode(b)
        if not payload:
            await self._delete(key)
            return False

        created_at = float(
            payload.get("__created_at") or payload.get("created_at") or 0.0
        )
        if created_at and self._expired(created_at, self._sess_cap):
            await self._delete(key)
            return False

        mutate(payload)
        payload["updated_at"] = self._now()
        payload.setdefault("__kind", "session")
        payload.setdefault("__created_at", created_at or self._now())
        
        try:
            await self._r.set(key, self._encode(payload), ex=int(ttl_sec))
        except (RedisError, RuntimeError):
            return False
        
        return True
