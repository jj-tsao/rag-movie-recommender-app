from __future__ import annotations

from .schemas import InteractionCreate, InteractionRecord, InteractionType
from .user_interactions_repo import SupabaseInteractionsRepo


class InteractionsService:
    def __init__(self, repo: SupabaseInteractionsRepo):
        self.repo = repo

    async def log_interaction(
        self,
        user_id: str,
        event: InteractionCreate,
    ) -> InteractionRecord:
        self._normalize_event(event)
        return await self.repo.create(user_id, event)

    def _normalize_event(self, event: InteractionCreate) -> None:
        # Clamp/cleanup; central place for invariants.
        if not event.media_id:
            raise ValueError("media_id is required")
        if not event.media_type:
            raise ValueError("media_type is required")

        # Example: coerce some types
        if event.event_type == InteractionType.REACTION and event.reaction is None:
            raise ValueError("reaction type is required for REACTION")
        if event.event_type == InteractionType.RATING and event.value is None:
            raise ValueError("value is required for RATE")

        if event.position is not None and event.position < 0:
            event.position = 0
