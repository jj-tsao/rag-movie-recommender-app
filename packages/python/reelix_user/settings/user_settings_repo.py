from __future__ import annotations
from anyio import to_thread
from .schemas import UserPreferencesUpsertResponse

TABLE_PREFS = "user_preferences"


class SupabaseUserSettingsRepo:
    def __init__(self, client):
        self.client = client

    # ---------- Async facade ----------
    async def upsert_preferences(
        self,
        user_id: str,
        *,
        genres_include: list[str],
        keywords_include: list[str],
    ) -> UserPreferencesUpsertResponse:
        return await to_thread.run_sync(
            self._upsert_preferences_sync, user_id, genres_include, keywords_include
        )

    # ---------- Private sync impls ----------
    def _upsert_preferences_sync(
        self,
        user_id: str,
        genres_include: list[str],
        keywords_include: list[str],
    ) -> UserPreferencesUpsertResponse:
        payload = {
            "user_id": user_id,
            "genres_include": genres_include,
            "keywords_include": keywords_include,
        }
        self.client.table(TABLE_PREFS).upsert(payload).execute()
        return UserPreferencesUpsertResponse(
            user_id=user_id,
            genres_include=genres_include,
            keywords_include=keywords_include,
        )
