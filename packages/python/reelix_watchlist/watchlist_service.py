from typing import Sequence, List
from .schemas import (
    WatchlistCreate,
    WatchlistUpdate,
    WatchlistItem,
    WatchlistRemoveById,
    WatchlistKey,
    KeysLookupOutItem,
    ExistsOut,
)
from .watchlist_repo import SupabaseWatchlistRepo
from .events import EventEmitter, NoopEmitter


class WatchlistService:
    def __init__(self, repo: SupabaseWatchlistRepo, events: EventEmitter | None = None):
        self.repo = repo
        self.events = events or NoopEmitter()

    async def add(self, dto: WatchlistCreate) -> WatchlistItem:
        item = await self.repo.create_or_revive(dto)
        await self.events.emit(
            "watchlist_add",
            {
                "user_id": dto.user_id,
                "media_id": dto.media_id,
                "media_type": dto.media_type,
                "status": item.status,
                "source": dto.source,
            },
        )
        return item

    async def update(self, dto: WatchlistUpdate) -> WatchlistItem:
        item = await self.repo.update(dto)
        await self.events.emit(
            "watchlist_update",
            {
                "user_id": dto.user_id,
                "id": dto.id,
                "status": dto.status,
                "rating": dto.rating,
            },
        )
        return item

    async def remove_by_id(self, dto: WatchlistRemoveById) -> WatchlistItem:
        item = await self.repo.remove_by_id(dto)
        await self.events.emit(
            "watchlist.remove",
            {
                "user_id": dto.user_id,
                "id": dto.id,
                "media_id": item.media_id,
                "media_type": item.media_type,
                "source": "watchlist",
            },
        )
        return item

    async def list(self, **kwargs):
        return await self.repo.list(**kwargs)

    async def batch_lookup(
        self, user_id: str, keys: Sequence[WatchlistKey]
    ) -> List[KeysLookupOutItem]:
        rows = await self.repo.batch_lookup(user_id, keys)
        return rows

    async def exists(self, user_id: str, media_id: int, media_type: str) -> ExistsOut:
        return await self.repo.exists(user_id, media_id, media_type)

    async def get(self, user_id: str, id: str) -> WatchlistItem:
        return await self.repo.get(user_id, id)
