from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from reelix_watchlist.schemas import (
    ExistsOut,
    KeysLookupOutItem,
    WatchlistCreate,
    WatchlistItem,
    WatchlistRemoveById,
    WatchlistUpdate,
)
from reelix_watchlist.watchlist_repo import SupabaseWatchlistRepo
from reelix_watchlist.watchlist_service import WatchlistService

from app.deps.supabase_client import get_current_user_id, get_supabase_client
from app.schemas import (
    KeysLookupRequest,
    WatchlistCreateRequest,
    WatchlistUpdateByIdRequest,
    WatchStatus,
)

router = APIRouter(prefix="/v2/users/me/watchlist", tags=["watchlist"])


def get_service(client=Depends(get_supabase_client)) -> WatchlistService:
    repo = SupabaseWatchlistRepo(client)
    return WatchlistService(repo)


# ---- Create ----
@router.post("", response_model=WatchlistItem, status_code=201)
async def create_item(
    req: WatchlistCreateRequest,
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    dto = WatchlistCreate(user_id=user_id, **req.model_dump(exclude_unset=True))
    return await service.add(dto)


# ---- Update (watch status, user rating, note) ----
@router.patch("/{id}", response_model=WatchlistItem)
async def update_item(
    id: str,
    req: WatchlistUpdateByIdRequest,
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    dto = WatchlistUpdate(
        user_id=user_id,
        id=id,
        rating_set=("rating" in req.model_fields_set),
        **req.model_dump(exclude_unset=True),
    )
    return await service.update(dto)


# ---- Delete (DB soft delete) ----
@router.delete("/{id}", response_model=WatchlistItem)
async def remove_by_id(
    id: str,
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    dto = WatchlistRemoveById(user_id=user_id, id=id)
    return await service.remove_by_id(dto)


class WatchlistPage(BaseModel):
    items: List[WatchlistItem]
    page: int
    page_size: int
    total: int


# ---- List ----
@router.get("", response_model=WatchlistPage)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    status: WatchStatus | None = Query(None),
    q: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    sort: str = "added_desc",
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    items, total = await service.list(
        user_id=user_id,
        status=status,
        q=q,
        year_min=year_min,
        year_max=year_max,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


# ---- Batch lookup by keys ----
@router.post("/keys/lookup", response_model=list[KeysLookupOutItem])
async def keys_lookup(
    req: KeysLookupRequest,
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    return await service.batch_lookup(user_id, req.keys)


# ---- Exists (declare BEFORE `/{id}` to avoid route shadowing) ----
@router.get("/exists", response_model=ExistsOut)
async def exists_item(
    media_id: int,
    media_type: str,
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    return await service.exists(user_id, media_id, media_type)


# ---- Get by id ----
@router.get("/{id}", response_model=WatchlistItem)
async def get_item(
    id: str,
    user_id: str = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_service),
):
    return await service.get(user_id, id)
