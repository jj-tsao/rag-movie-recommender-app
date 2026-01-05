from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from reelix_core.types import MediaType


class WatchStatus(str, Enum):
    WANT = "want"
    WATCHED = "watched"


class WatchlistCreate(BaseModel):
    user_id: str
    media_id: int
    media_type: Literal["movie", "tv"]
    status: WatchStatus = WatchStatus.WANT
    title: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    trailer_url: str | None = None
    release_year: int | None = None
    genres: list[str] | None = None
    imdb_rating: float | None = None
    rt_rating: int | None = None
    why_summary: str | None = None
    source: str | None = None


class WatchlistUpdate(BaseModel):
    user_id: str
    id: str
    media_id: int | None = None
    status: WatchStatus | None = None
    rating: int | None = Field(default=None, ge=1, le=10)
    rating_set: bool = False
    notes: str | None = None


class WatchlistRemoveById(BaseModel):
    user_id: str
    id: str


class WatchlistKey(BaseModel):
    media_type: MediaType = MediaType.MOVIE
    media_id: int


class KeysLookupOutItem(WatchlistKey):
    exists: bool
    id: str | None = None
    status: WatchStatus | None = None
    rating: int | None = None


class ExistsOut(BaseModel):
    exists: bool
    id: str | None = None
    status: WatchStatus = WatchStatus.WANT
    rating: int | None = None


class WatchlistItem(BaseModel):
    user_id: str
    id: str
    media_id: int
    media_type: str
    status: WatchStatus
    rating: int | None = None
    notes: str | None = None
    title: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    trailer_url: str | None = None
    release_year: int | None = None
    genres: list[str] | None = None
    imdb_rating: float | None = None
    rt_rating: int | None = None
    why_summary: str | None = None
    source: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None
    is_active: bool
