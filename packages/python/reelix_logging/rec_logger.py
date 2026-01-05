from __future__ import annotations

import time
from typing import Any, Literal, Mapping

import httpx
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from reelix_ranking.types import Candidate, ScoreTrace
from reelix_core.types import QueryFilter

Endpoint = Literal[
    "discovery/for-you",
    "discovery/explore",
    "recommendations/interactive",
]


# ---------- Public models (optional typing nicety) ----------
class DeviceInfo(BaseModel):
    device_type: str | None = None
    platform: str | None = None
    user_agent: str | None = None


class FinalRec(BaseModel):
    media_id: int
    why: str


# ---------- Core logger ----------
class TelemetryLogger:
    """
    One shared logger for discovery & recommendations.

    - rec_queries: one row per request
    - rec_results: one row per ranked candidate
    - rec_stream_events: optional SSE lifecycle (started | why_delta | done | error)
    - rec_recommendations_ext: extension for /recommendations (e.g., query_text)

    Usage (examples at bottom):
      logger = RecLogger.from_env(sample=1.0)
      await logger.log_query_started(endpoint="discover", ...)
      await logger.log_candidates(endpoint="discover", query_id=..., candidates=[...])
      agg = logger.start_stream(endpoint="discover", query_id=..., batch_id=1)
      await agg.flush_started(); agg.add_delta(media_id, len_bytes); await agg.flush_delta(); await agg.flush_done()
    """

    def __init__(
        self,
        supabase_url: str,
        api_key: str,
        client,
        *,
        sample: float = 1.0,
        timeout_s: float = 5.0,
    ):
        self.supabase_url = supabase_url.rstrip("/")
        self.api_key = api_key
        self.client = client
        self.sample = float(max(0.0, min(1.0, sample)))
        self.timeout_s = timeout_s

    def _enabled(self) -> bool:
        return bool(self.supabase_url and self.api_key and self.sample > 0)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

    async def _post(
        self, client: httpx.AsyncClient, path: str, payload: list[dict[str, Any]]
    ) -> None:
        if not self._enabled() or not payload:
            return
        try:
            r = await client.post(
                f"{self.supabase_url}/rest/v1/{path}",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout_s,
            )
            if r.status_code not in (200, 201, 204):
                print(
                    f"⚠️ rec_logger POST {path} failed {r.status_code}: {r.text}"
                )
        except Exception as e:
            print(f"❌ rec_logger POST {path} error: {e}")

    @staticmethod
    def to_jsonable(x):
        return jsonable_encoder(x, exclude_none=True)

    # ---------- Public APIs ----------
    async def log_query_intake(
        self,
        *,
        endpoint: Endpoint,
        query_id: str,
        user_id: str | None = None,
        session_id: str | None = None,
        media_type: str,
        query_text: str | None = None,
        query_filters: QueryFilter | None = None,
        ctx_log: dict[str, Any] | None = None,
        pipeline_version: str | None,
        batch_size: int,
        device_info: DeviceInfo | None = None,
        request_meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Insert into rec_queries (one row).
        """
        if not self._enabled():
            return
        meta = dict(request_meta or {})
        if device_info is not None:
            meta["device"] = device_info.model_dump()

        row = {
            "endpoint": endpoint,
            "query_id": query_id,
            "user_id": user_id,
            "session_id": session_id,
            "media_type": media_type,
            "ctx_log": ctx_log,
            "pipeline_version": pipeline_version,
            "batch_size": int(batch_size),
            "request_meta": meta,
        }
        if query_text:
            row["query_text"] = query_text
        if query_filters:
            row["query_filters"] = self.to_jsonable(query_filters)

        async with httpx.AsyncClient() as client:
            await self._post(client, "rec_queries", [row])

    async def log_candidates(
        self,
        *,
        endpoint: Endpoint,
        query_id: str,
        media_type: str,
        candidates: list[Candidate],
        traces: Mapping[int, ScoreTrace],
        stage: str,
    ) -> None:
        """
        Insert N rows into rec_results.
        """
        if not self._enabled():
            return
        rows = []
        for r, c in enumerate(candidates, start=1):
            cid = c.id
            trace = traces.get(cid)
            row = {
                "endpoint": endpoint,
                "query_id": query_id,
                "media_type": media_type,
                "media_id": cid,
                "rank": r,
                "title": c.payload.get("title"),
                "score_final": trace.final_score if trace else None,
                "score_dense": trace.dense_score if trace else None,
                "score_sparse": trace.sparse_score if trace else None,
                "meta_breakdown": self.to_jsonable(trace.meta_breakdown)
                if trace
                else None,
                "stage": stage,
            }
            rows.append(row)
        if not rows:
            return
        async with httpx.AsyncClient() as client:
            await self._post(client, "rec_results", rows)

    async def log_why(
        self,
        *,
        endpoint: str,
        query_id: str,
        final_recs: list[FinalRec],
    ) -> None:
        """
        Update interactive mode final recs per row.
        """
        if not self._enabled():
            return
        rows = []
        for r in final_recs:
            row = {
                "endpoint": endpoint,
                "query_id": query_id,
                "media_id": r.media_id,
                "stage": "final",
                "why_summary": r.why,
            }
            rows.append(row)
        if not rows:
            return
        async with httpx.AsyncClient() as client:
            await self._post(client, "rec_results?on_conflict=endpoint,query_id,media_id", rows)

    def start_stream(
        self, *, endpoint: Endpoint, query_id: str, batch_id: int | None
    ) -> "StreamAggregator":
        return StreamAggregator(
            logger=self, endpoint=endpoint, query_id=query_id, batch_id=batch_id
        )

    async def upsert_session(
        self,
        *,
        session_id: str,
        hashed_user_id: str | None,
        device: DeviceInfo | None = None,
    ) -> None:
        """
        Optional: maintain rec_client_sessions by session_id.
        """
        if not self._enabled():
            return
        row = {
            "session_id": session_id,
            "hashed_user_id": hashed_user_id,
            "last_seen": "now()",
            "request_count": 1,
        }
        if device is not None:
            data = device.model_dump()
            row["device_type"] = data.get("device_type")
            row["platform"] = data.get("platform")
            row["user_agent"] = data.get("user_agent")
        async with httpx.AsyncClient() as client:
            await self._post(client, "rec_client_sessions", [row])


# ---------- SSE stream aggregator ----------
class StreamAggregator:
    """
    Best-effort, non-blocking tracker for SSE phases:
      started -> multiple why_delta aggregates -> done | error
    """

    def __init__(
        self,
        logger: TelemetryLogger,
        *,
        endpoint: Endpoint,
        query_id: str,
        batch_id: int | None,
    ):
        self.logger = logger
        self.endpoint = endpoint
        self.query_id = query_id
        self.batch_id = batch_id
        self.media_stats: dict[
            str, dict[str, int]
        ] = {}  # media_id -> {chunk_count, bytes_total}
        self.t0 = time.time()

    def add_delta(self, media_id: str, chunk_bytes: int) -> None:
        st = self.media_stats.setdefault(media_id, {"chunk_count": 0, "bytes_total": 0})
        st["chunk_count"] += 1
        st["bytes_total"] += max(0, int(chunk_bytes))

    async def flush_started(self) -> None:
        await self._write(
            [
                {
                    "endpoint": self.endpoint,
                    "query_id": self.query_id,
                    "batch_id": self.batch_id,
                    "event": "started",
                }
            ]
        )

    async def flush_delta(self) -> None:
        if not self.media_stats:
            return
        rows = []
        for mid, st in self.media_stats.items():
            rows.append(
                {
                    "endpoint": self.endpoint,
                    "query_id": self.query_id,
                    "batch_id": self.batch_id,
                    "event": "why_delta",
                    "media_id": mid,
                    "chunk_count": st["chunk_count"],
                    "bytes_total": st["bytes_total"],
                }
            )
        self.media_stats.clear()
        await self._write(rows)

    async def flush_done(self, error_message: str | None = None) -> None:
        dur_ms = int((time.time() - self.t0) * 1000)
        row = {
            "endpoint": self.endpoint,
            "query_id": self.query_id,
            "batch_id": self.batch_id,
            "event": "error" if error_message else "done",
            "duration_ms": dur_ms,
            "error_message": error_message,
        }
        await self._write([row])

    async def _write(self, rows: list[dict[str, Any]]) -> None:
        if not self.logger._enabled() or not rows:
            return
        async with httpx.AsyncClient() as client:
            await self.logger._post(client, "rec_stream_events", rows)
