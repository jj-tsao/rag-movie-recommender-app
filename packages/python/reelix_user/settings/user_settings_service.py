from __future__ import annotations
from .user_settings_repo import SupabaseUserSettingsRepo
from .schemas import UserPreferencesUpsertResponse


class UserSettingsService:
    def __init__(
        self,
        repo: SupabaseUserSettingsRepo,
    ):
        self.repo = repo

    # Upsert preferences
    async def upsert_preferences(
        self,
        user_id: str,
        *,
        genres_include: list[str],
        keywords_include: list[str],
    ) -> UserPreferencesUpsertResponse:
        return await self.repo.upsert_preferences(
            user_id, genres_include=genres_include, keywords_include=keywords_include
        )
