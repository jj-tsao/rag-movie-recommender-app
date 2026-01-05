from __future__ import annotations

from typing import List, Any

from pydantic import BaseModel, Field, field_validator
from reelix_core.types import MediaType, QueryFilter
from reelix_user.taste.schemas import TasteProfileMeta
from reelix_watchlist.schemas import WatchStatus, WatchlistKey
from reelix_user.interactions.schemas import InteractionType


class ChatMessage(BaseModel):
    role: str
    content: str


class DeviceInfo(BaseModel):
    device_type: str | None = None
    platform: str | None = None
    user_agent: str | None = None


class DiscoverRequest(BaseModel):
    media_type: MediaType = MediaType.MOVIE
    page: int = 1
    page_size: int = 20
    query_filters: QueryFilter = Field(default_factory=QueryFilter)
    include_llm_why: bool = True  # if true, returns markdown “why” in JSON
    session_id: str
    query_id: str
    device_info: DeviceInfo | None = None


class InteractiveRequest(BaseModel):
    media_type: MediaType = MediaType.MOVIE
    query_text: str = Field(
        ...,
        examples=[
            "Mind-bending sci-fi with philosophical undertones and existential stakes"
        ],
    )
    # history: List[ChatMessage] | None = Field(default_factory=list, examples=[[]])
    query_filters: QueryFilter = Field(default_factory=QueryFilter)
    session_id: str
    query_id: str
    device_info: DeviceInfo | None = None

    @field_validator("query_text")
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class ExploreRerunPatch(BaseModel):
    # If field is omitted => keep existing.
    # If field is present as null => clear.
    # If field is present as [] or list => replace with exactly that list.
    providers: list[str] | None = Field(default=None)
    year_range: tuple[int, int] | None = Field(default=None) 


class ExploreRerunRequest(BaseModel):
    session_id: str
    query_id: str
    device_info: dict | None = None
    patch: ExploreRerunPatch = Field(default_factory=ExploreRerunPatch)


class FinalRec(BaseModel):
    media_id: int
    why: str
    imdb_rating: float | None = None
    rt_rating: int | None = None
    why_source: str  # "cache" or "llm"


class FinalRecsRequest(BaseModel):
    query_id: str
    media_type: MediaType
    final_recs: List[FinalRec]


class TasteProfileExistsOut(TasteProfileMeta):
    has_profile: bool = True  # route returns 200 only when it exists


class TasteProfileRebuildRequest(BaseModel):
    media_type: MediaType = MediaType.MOVIE


class UserPreferencesUpsertRequest(BaseModel):
    genres_include: list[str] = Field(default_factory=list)
    keywords_include: list[str] = Field(default_factory=list)


class WatchlistCreateRequest(BaseModel):
    media_id: int
    media_type: MediaType = MediaType.MOVIE
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


class KeysLookupRequest(BaseModel):
    keys: list[WatchlistKey] = Field(..., min_length=1, max_length=200)


class WatchlistUpdateByIdRequest(BaseModel):
    status: WatchStatus | None = None
    rating: int | None = Field(None, ge=1, le=10)
    notes: str | None = None


class InteractionsCreateRequest(BaseModel):
    media_type: MediaType
    media_id: int
    title: str
    event_type: InteractionType
    reaction: str | None = None
    value: float | None = None
    position: int | None = None
    source: str | None = None
    query_id: str | None = None
    session_id: str | None = None
    context_json: dict[str, Any] | None = None
    idempotency_key: str | None = None
