from __future__ import annotations

from reelix_core.types import MediaType, UserSignals, UserTasteContext
from .user_context_repo import SupabaseUserContextRepo


class UserContextService:
    def __init__(
        self,
        repo: SupabaseUserContextRepo,
    ):
        self.repo = repo

    async def fetch_user_signals(
        self, user_id: str, media_type: MediaType
    ) -> UserSignals:
        return await self.repo.fetch_user_signals(user_id, media_type)
    
    async def fetch_user_taste_context(
        self, user_id: str, media_type: MediaType
    ) -> UserTasteContext:
        return await self.repo.fetch_user_taste_context(user_id, media_type)
