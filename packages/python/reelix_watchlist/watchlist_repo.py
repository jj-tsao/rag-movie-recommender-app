from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from anyio import to_thread
from postgrest.exceptions import APIError as PostgrestAPIError

from reelix_core.errors import NotFound, Conflict, Forbidden
from .schemas import (
    ExistsOut,
    WatchlistCreate,
    WatchlistItem,
    WatchlistRemoveById,
    WatchlistUpdate,
    WatchStatus,
    WatchlistKey,
    KeysLookupOutItem,
)

TABLE = "user_watchlist"
DENORM_FIELDS = {
    "title",
    "poster_url",
    "backdrop_url",
    "release_year",
    "genres",
    "why_summary",
    "source",
    "imdb_rating",
    "rt_rating",
}
MAX_IN = 200  # keep matches PostgREST URL/param safety


def _row_to_item(row: dict) -> WatchlistItem:
    return WatchlistItem(**row)


def _map_pgrest(e: PostgrestAPIError) -> Exception:
    code = getattr(e, "code", None) or ""
    # Postgres / PostgREST error codes:
    # 23505 unique_violation, 42501 insufficient_privilege (RLS), 23503 foreign_key_violation
    if code == "23505":
        return Conflict("duplicate")
    if code == "42501":
        return Forbidden("permission denied")
    if code == "23503":
        return Conflict("foreign key violation")
    return e  # let unexpected ones bubble up to 500


class SupabaseWatchlistRepo:
    def __init__(self, client):
        self.client = client

    # ---------- Async facade (runs sync work in threadpool) ----------
    async def create_or_revive(self, dto: WatchlistCreate) -> WatchlistItem:
        return await to_thread.run_sync(self._create_revive_sync, dto)

    async def update(self, dto: WatchlistUpdate) -> WatchlistItem:
        return await to_thread.run_sync(self._update_sync, dto)

    async def remove_by_id(self, dto: WatchlistRemoveById) -> WatchlistItem:
        return await to_thread.run_sync(self._remove_by_id_sync, dto)

    async def list(
        self,
        user_id: str,
        *,
        status: WatchStatus | None,
        q: str | None,
        year_min: int | None,
        year_max: int | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[WatchlistItem], int]:
        return await to_thread.run_sync(
            self._list_sync,
            user_id,
            status,
            q,
            year_min,
            year_max,
            sort,
            page,
            page_size,
        )

    async def batch_lookup(
        self, user_id: str, keys: Sequence[WatchlistKey]
    ) -> list[KeysLookupOutItem]:
        return await to_thread.run_sync(self._batch_lookup_sync, user_id, keys)

    async def exists(self, user_id: str, media_id: int, media_type: str) -> ExistsOut:
        return await to_thread.run_sync(
            self._exists_sync, user_id, media_id, media_type
        )

    async def get(self, user_id: str, id: str) -> WatchlistItem:
        return await to_thread.run_sync(self._get_sync, user_id, id)

    # ---------- Private sync implementations ----------
    def _create_revive_sync(self, dto: WatchlistCreate) -> WatchlistItem:
        payload = dto.model_dump(exclude_none=True)

        # 0) Active exists? return as-is
        existing = (
            self.client.table(TABLE)
            .select("*")
            .eq("user_id", dto.user_id)
            .eq("media_id", dto.media_id)
            .eq("media_type", dto.media_type)
            .is_("deleted_at", None)
            .limit(1)
            .execute()
        )
        if existing.data:
            current = existing.data[0]
            updates: dict[str, object] = {}
            for field in ("imdb_rating", "rt_rating"):
                if field in payload and payload[field] is not None and current.get(field) != payload[field]:
                    updates[field] = payload[field]

            if updates:
                try:
                    updated = (
                        self.client.table(TABLE)
                        .update(updates, returning="representation")
                        .eq("user_id", dto.user_id)
                        .eq("media_id", dto.media_id)
                        .eq("media_type", dto.media_type)
                        .is_("deleted_at", None)
                        .execute()
                    )
                except PostgrestAPIError as e:
                    raise _map_pgrest(e)

                if updated.data:
                    return _row_to_item(updated.data[0])
                current.update(updates)
            return _row_to_item(current)

        # 1) Revive a soft-deleted row
        revive_updates = {"deleted_at": None, "deleted_reason": None}
        for k in DENORM_FIELDS:
            if k in payload:
                revive_updates[k] = payload[k]

        try:
            revived = (
                self.client.table(TABLE)
                .update(revive_updates, returning="representation")
                .eq("user_id", dto.user_id)
                .eq("media_id", dto.media_id)
                .eq("media_type", dto.media_type)
                .not_.is_("deleted_at", None)
                .execute()
            )
        except PostgrestAPIError as e:
            raise _map_pgrest(e)

        if revived.data:
            return _row_to_item(revived.data[0])

        # 2) Fresh insert (handle race 23505 → read active)
        try:
            res = (
                self.client.table(TABLE)
                .insert(payload, returning="representation")
                .execute()
            )
            return _row_to_item(res.data[0])
        except PostgrestAPIError as e:
            mapped = _map_pgrest(e)
            if isinstance(mapped, Conflict):  # 23505 race: someone inserted
                final = (
                    self.client.table(TABLE)
                    .select("*")
                    .eq("user_id", dto.user_id)
                    .eq("media_id", dto.media_id)
                    .eq("media_type", dto.media_type)
                    .is_("deleted_at", None)
                    .limit(1)
                    .execute()
                )
                if final.data:
                    return _row_to_item(final.data[0])
            raise mapped

    def _update_sync(self, dto: WatchlistUpdate) -> WatchlistItem:
        # 1) Ensure the row exists AND is not soft-deleted
        exists = (
            self.client.table(TABLE)
            .select("id")  # small projection
            .eq("id", dto.id)
            .eq("user_id", dto.user_id)
            .is_("deleted_at", None)
            .limit(1)
            .execute()
        )
        if not exists.data:
            raise NotFound("watchlist item not found")

        # 2) Build allowed updates (no deleted_at changes here)
        updates: dict[str, object] = {}
        if dto.status is not None:
            updates["status"] = (
                dto.status.value if hasattr(dto.status, "value") else dto.status
            )
        if dto.rating_set:   
            updates["rating"] = dto.rating   # may be None → sets NULL in DB
        if dto.notes is not None:
            updates["notes"] = dto.notes

        # No-op: return current row
        if not updates:
            current = (
                self.client.table(TABLE)
                .select("*")
                .eq("id", dto.id)
                .eq("user_id", dto.user_id)
                .is_("deleted_at", None)
                .limit(1)
                .execute()
            )
            if not current.data:
                raise NotFound("watchlist item not found")
            return _row_to_item(current.data[0])

        # 3) Apply update and return the updated row
        try:
            res = (
                self.client.table(TABLE)
                .update(updates, returning="representation")
                .eq("id", dto.id)
                .eq("user_id", dto.user_id)
                .is_("deleted_at", None)
                .execute()
            )
        except PostgrestAPIError as e:
            raise _map_pgrest(e)

        if not res.data:
            raise NotFound("watchlist item not found")

        return _row_to_item(res.data[0])

    def _remove_by_id_sync(self, dto: WatchlistRemoveById) -> WatchlistItem:
        try:
            res = (
                self.client.table(TABLE)
                .update(
                    {
                        "status": "want",
                        "rating": None,
                        "deleted_at": datetime.now(timezone.utc).isoformat(),
                        "deleted_reason": "user_removed",
                    },
                    returning="representation",
                )
                .eq("id", dto.id)
                .eq("user_id", dto.user_id)
                .is_("deleted_at", None)  # only active rows
                .execute()
            )
        except PostgrestAPIError as e:
            raise _map_pgrest(e)

        data = res.data or []
        if not data:
            raise NotFound("watchlist item not found")
        return _row_to_item(data[0])

    def _list_sync(
        self,
        user_id: str,
        status: WatchStatus | None,
        q: str | None,
        year_min: int | None,
        year_max: int | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[WatchlistItem], int]:
        qb = (
            self.client.table(TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
            .is_("deleted_at", None)
        )
        if status:
            status_str = status.value if isinstance(status, WatchStatus) else status
            qb = qb.eq("status", status_str)
        if q:
            qb = qb.ilike("title", f"%{q}%")
        if year_min is not None:
            qb = qb.gte("release_year", year_min)
        if year_max is not None:
            qb = qb.lte("release_year", year_max)

        sort_map = {
            "added_desc": ("created_at", True),
            "added_asc": ("created_at", False),
            "year_desc": ("release_year", True),
            "year_asc": ("release_year", False),
            "rating_desc": ("rating", True),
            "rating_asc": ("rating", False),
        }

        col, desc = sort_map.get(sort, ("created_at", True))

        if col == "rating":
            # Prefer explicit NULLS LAST for rating sorts
            try:
                qb = qb.order("rating", desc=desc, nullslast=True)  # newer clients
            except TypeError:
                if desc:
                    qb = qb.order("rating", desc=True, nullsfirst=False)  # fallback
                else:
                    qb = qb.order("rating", desc=False)
        else:
            qb = qb.order(col, desc=desc)

        start = (page - 1) * page_size
        end = start + page_size - 1
        res = qb.range(start, end).execute()

        items = [_row_to_item(r) for r in (res.data or [])]
        total = res.count or 0
        return items, total

    def _batch_lookup_sync(
        self, user_id: str, keys: Sequence[WatchlistKey]
    ) -> list[KeysLookupOutItem]:
        # Build a set of unique keys and group by media_type for efficient queries
        unique_keys = []
        seen = set()
        for k in keys:
            tup = (k.media_type, k.media_id)
            if tup not in seen:
                unique_keys.append(tup)
                seen.add(tup)

        # Group by type
        by_type: dict[str, list[int]] = {"movie": [], "tv": []}
        for mt, mid in unique_keys:
            by_type.setdefault(mt, []).append(mid)

        # Fetch rows per type (chunk if large)
        rows_map: dict[tuple[str, int], dict] = {}
        for mt, ids in by_type.items():
            if not ids:
                continue
            for i in range(0, len(ids), MAX_IN):
                chunk = ids[i : i + MAX_IN]
                res = (
                    self.client.table(TABLE)
                    .select("id,media_id,media_type,status,rating")
                    .eq("user_id", user_id)
                    .eq("media_type", mt)
                    .is_("deleted_at", None)
                    .in_("media_id", chunk)
                    .execute()
                )
                for r in res.data or []:
                    rows_map[(r["media_type"], int(r["media_id"]))] = r

        # Build output preserving input order
        out: list[KeysLookupOutItem] = []
        for k in keys:
            row = rows_map.get((k.media_type, k.media_id))
            if not row:
                out.append(
                    KeysLookupOutItem(
                        media_type=k.media_type,
                        media_id=k.media_id,
                        exists=False,
                        id=None,
                        status=None,
                        rating=None,
                    )
                )
            else:
                # Cast status string to Enum
                try:
                    status_enum = WatchStatus(row["status"])
                except Exception:
                    status_enum = None
                out.append(
                    KeysLookupOutItem(
                        media_type=k.media_type,
                        media_id=k.media_id,
                        exists=True,
                        id=row["id"],
                        status=status_enum,
                        rating=row.get("rating"),
                    )
                )
        return out

    def _exists_sync(self, user_id: str, media_id: int, media_type: str) -> ExistsOut:
        res = (
            self.client.table(TABLE)
            .select("id,status,rating")
            .eq("user_id", user_id)
            .eq("media_id", media_id)
            .eq("media_type", media_type)
            .is_("deleted_at", None)  # active rows only
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return ExistsOut(exists=False)

        row = rows[0]
        status = self._to_watch_status(row.get("status"))
        return ExistsOut(
            exists=True,
            id=row.get("id"),
            status=status,
            rating=row.get("rating"),
        )

    def _to_watch_status(self, value: str | None = None) -> WatchStatus:
        try:
            return WatchStatus(value) if value is not None else WatchStatus.WANT
        except ValueError:
            return WatchStatus.WANT

    def _get_sync(self, user_id: str, id: str) -> WatchlistItem:
        res = (
            self.client.table(TABLE)
            .select("*")
            .eq("id", id)
            .eq("user_id", user_id)
            .execute()
        )
        if not res.data:
            raise NotFound("watchlist item not found")
        return _row_to_item(res.data[0])
