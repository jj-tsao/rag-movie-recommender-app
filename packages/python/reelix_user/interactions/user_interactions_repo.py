from __future__ import annotations

from anyio import to_thread
from postgrest.exceptions import APIError as PostgrestAPIError
from reelix_core.errors import Conflict, Forbidden

from .schemas import InteractionCreate, InteractionRecord

TABLE = "user_interactions"
MAX_LIMIT = 5000  # safety cap for taste fetch etc.


def _row_to_item(row: dict) -> InteractionRecord:
    return InteractionRecord(**row)


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


class SupabaseInteractionsRepo:
    def __init__(self, client):
        self.client = client

    # ---------- Async facade ----------
    async def create(
        self,
        user_id: str,
        event: InteractionCreate,
    ) -> InteractionRecord:
        return await to_thread.run_sync(self._create_sync, user_id, event)

    # ---------- Private sync impls ----------

    def _create_sync(self, user_id: str, event: InteractionCreate) -> InteractionRecord:
        payload = event.model_dump(exclude_none=True)
        payload["user_id"] = user_id

        # If idempotency_key present → upsert on (user_id, idempotency_key)
        try:
            if event.idempotency_key:
                payload["idempotency_key"] = event.idempotency_key
                res = (
                    self.client.table(TABLE)
                    .upsert(
                        payload,
                        on_conflict="user_id,idempotency_key",
                        returning="representation",
                    )
                    .execute()
                )
            else:
                res = (
                    self.client.table(TABLE)
                    .insert(payload, returning="representation")
                    .execute()
                )
        except PostgrestAPIError as e:
            raise _map_pgrest(e)

        rows = res.data or []
        if not rows:
            # returning="representation" expects rows; if not, treat as conflict
            raise Conflict("interaction not created")

        return _row_to_item(rows[0])
