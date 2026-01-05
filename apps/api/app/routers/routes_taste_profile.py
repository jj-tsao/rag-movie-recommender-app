from fastapi import APIRouter, Depends, HTTPException
from reelix_core.types import MediaType
from reelix_user.taste.embedding_store import QdrantEmbeddingStore
from reelix_user.taste.taste_profile_repo import SupabaseTasteProfileRepo
from reelix_user.taste.taste_profile_service import TasteProfileService

from app.deps.deps import get_qdrant
from app.deps.supabase_client import (
    get_current_user_id,
    get_supabase_client,
    get_user_context_service,
)
from app.schemas import (
    TasteProfileExistsOut,
)

router = APIRouter(prefix="/v2/users/me/taste_profile", tags=["taste"])


def get_service(
    sb=Depends(get_supabase_client),
    user_context=Depends(get_user_context_service),
    qdrant=Depends(get_qdrant),
) -> TasteProfileService:
    repo = SupabaseTasteProfileRepo(sb)
    embeddings = QdrantEmbeddingStore(qdrant)
    return TasteProfileService(repo, user_context, embeddings)


# Check taste profile existence (404 when missing)
@router.get("", response_model=TasteProfileExistsOut)
async def get_my_taste_profile(
    media_type: MediaType = MediaType.MOVIE,
    user_id: str = Depends(get_current_user_id),
    service: TasteProfileService = Depends(get_service),
):
    meta = await service.get_meta(user_id, media_type)
    if not meta:
        # important: ForYouPage expects 404 when no profile exists
        raise HTTPException(status_code=404, detail="Taste profile not found")
    return TasteProfileExistsOut(**meta.model_dump(), has_profile=True)


# Rebuild taste profile
@router.post("/rebuild")
async def rebuild_taste_profile(
    # req: TasteProfileRebuildRequest,
    user_id: str = Depends(get_current_user_id),
    service: TasteProfileService = Depends(get_service),
):
    result = await service.rebuild(user_id, media_type=MediaType.MOVIE)
    # Return small meta so client can choose to refresh its feed
    return {"ok": True, "meta": result}
