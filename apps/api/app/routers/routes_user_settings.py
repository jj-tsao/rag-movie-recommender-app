from fastapi import APIRouter, Depends
from reelix_user.settings.schemas import UserPreferencesUpsertResponse
from reelix_user.settings.user_settings_repo import SupabaseUserSettingsRepo
from reelix_user.settings.user_settings_service import UserSettingsService

from app.schemas import UserPreferencesUpsertRequest
from app.deps.supabase_client import (
    get_current_user_id,
    get_supabase_client,
)

router = APIRouter(prefix="/v2/users/me/settings", tags=["settings"])


def get_service(
    sb=Depends(get_supabase_client),
) -> UserSettingsService:
    repo = SupabaseUserSettingsRepo(sb)
    return UserSettingsService(repo)


# Upsert genres/keywords into user_preferences
@router.patch("/preferences", response_model=UserPreferencesUpsertResponse)
async def upsert_preferences(
    req: UserPreferencesUpsertRequest,
    user_id: str = Depends(get_current_user_id),
    service: UserSettingsService = Depends(get_service),
):
    return await service.upsert_preferences(
        user_id,
        genres_include=req.genres_include,
        keywords_include=req.keywords_include,
    )
