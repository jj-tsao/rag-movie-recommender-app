from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from redis.asyncio import Redis

JsonObj = dict[str, Any]
MutateFn = Callable[[Any], None]


@dataclass
class Ticket:
    """
    Ticket payload.

    - user_id: used for auth checks on /why
    - prompts: fully-rendered LLM calls or a minimal spec to rebuild
    - created_at: epoch seconds (float); used for absolute TTL capping
    - meta: optional small traceability blob (recipe, prompt_hash, items_brief)
    """

    user_id: str
    prompts: Any
    created_at: float | None = None
    meta: JsonObj | None = None

    def ensure_created(self) -> None:
        if self.created_at is None:
            self.created_at = time.time()


class TicketStore:
    """
    Redis-backed store with gzip'd JSON payloads.
    - Sliding TTL via touch()
    - Absolute TTL cap to avoid zombies (based on Ticket.created_at)
    """

    def __init__(
        self,
        *,
        client: Redis,
        namespace: str = "reelix:ticket:",
        absolute_ttl_sec: int = 60 * 60,  # 1 hour cap
        compression_level: int = 5,
    ) -> None:
        self._r = client
        self._ns = namespace
        self._abs_ttl = int(absolute_ttl_sec)
        self._level = int(compression_level)

    def _k(self, key: str) -> str:
        return f"{self._ns}{key}"

    # ---- serialization helpers ----

    def _serialize(self, ticket: Ticket) -> bytes:
        ticket.ensure_created()
        payload: JsonObj = {
            "user_id": ticket.user_id,
            "prompts": ticket.prompts,
            "created_at": ticket.created_at,
        }
        if ticket.meta is not None:
            payload["meta"] = ticket.meta
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        return gzip.compress(raw, compresslevel=self._level)

    def _deserialize(self, blob: bytes) -> Ticket | None:
        try:
            raw = gzip.decompress(blob)
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return None

        created_at = float(data.get("created_at", 0.0) or 0.0)
        if self._abs_ttl and created_at and (time.time() - created_at) > self._abs_ttl:
            # Let caller delete; just signal expired by returning None
            return None

        return Ticket(
            user_id=str(data.get("user_id", "")),
            prompts=data.get("prompts"),
            created_at=created_at or time.time(),
            meta=data.get("meta") if isinstance(data.get("meta"), dict) else None,
        )

    # ---- API ----

    async def put(self, key: str, ticket: Ticket, ttl_sec: int) -> None:
        b = self._serialize(ticket)
        await self._r.set(self._k(key), b, ex=int(ttl_sec))

    async def get(self, key: str) -> Ticket | None:
        b = await self._r.get(self._k(key))
        if not b:
            return None
        ticket = self._deserialize(b)
        if ticket is None:
            # Absolute TTL exceeded or decode error: clean up
            await self.delete(key)
            return None
        return ticket

    async def delete(self, key: str) -> None:
        await self._r.delete(self._k(key))

    async def touch(self, key: str, ttl_sec: int) -> bool:
        # Refresh idle TTL (sliding)
        res = await self._r.expire(self._k(key), int(ttl_sec))
        return bool(res)

    async def update(self, key: str, ttl_sec: int, mutate: MutateFn) -> bool:
        """
        Read-modify-write with TTL refresh. Not atomic across processes.
        If you need atomicity, wrap with a short-lived Lua script or a
        simple optimistic lock using GET/SETNX of a lock key.
        """
        k = self._k(key)
        blob = await self._r.get(k)
        if not blob:
            return False

        # Enforce absolute cap (same semantics as get())
        ticket = self._deserialize(blob)
        if ticket is None:
            await self._r.delete(k)
            return False

        try:
            raw = gzip.decompress(blob)
            data = json.loads(raw.decode("utf-8"))
            mutate(data)  # mutate in-place
            new_blob = gzip.compress(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                ),
                compresslevel=self._level,
            )
        except Exception:
            return False

        await self._r.set(k, new_blob, ex=int(ttl_sec))
        return True

    async def aclose(self) -> None:
        # If you're sharing a single Redis client app-wide,
        # you may choose NOT to call this here.
        try:
            await self._r.aclose()
        except Exception:
            pass
