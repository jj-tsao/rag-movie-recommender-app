from fastapi import APIRouter, Depends
from reelix_user.interactions.user_interactions_repo import SupabaseInteractionsRepo
from reelix_user.interactions.user_interactions_service import InteractionsService
from reelix_user.interactions.schemas import InteractionCreate


from app.deps.supabase_client import (
    get_current_user_id,
    get_supabase_client,
)
from app.schemas import InteractionsCreateRequest

router = APIRouter(prefix="/v2/interactions", tags=["interactions"])


def get_service(
    sb=Depends(get_supabase_client),
) -> InteractionsService:
    repo = SupabaseInteractionsRepo(sb)
    return InteractionsService(repo)


@router.post("", status_code=201)
async def create_interaction(
    req: InteractionsCreateRequest,  # Pydantic → maps to InteractionCreate
    user_id: str = Depends(get_current_user_id),
    service: InteractionsService = Depends(get_service),
):
    event = InteractionCreate(
        **req.model_dump(),
    )
    rec = await service.log_interaction(
        user_id=user_id,
        event=event,
    )
    return rec
