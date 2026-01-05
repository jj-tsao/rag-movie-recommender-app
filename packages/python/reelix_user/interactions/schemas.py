from __future__ import annotations
from pydantic import BaseModel
from enum import Enum
from typing import Any
from reelix_core.types import MediaType


class InteractionType(str, Enum):
    IMPRESSION = "impression"
    REACTION = "rec_reaction"  # love/like/dislike for recs & onboarding
    ADD_TO_WATCHLIST = "add_to_watchlist"
    REMOVE_FROM_WATCHLIST = "remove_from_watchlist"
    MARK_WATCHED = "mark_watched"
    RATING = "rating"  # 1–10 stars post-watch
    TRAILER_VIEW = "trailer_view"
    DISMISS = "dismiss"
    SHARE = "share"
    SUBS_UPDATE = "subs_update"
    SETTINGS_CHANGE = "settings_change"


class InteractionCreate(BaseModel):
    media_type: MediaType
    media_id: int
    title: str
    event_type: InteractionType
    reaction: str | None = None
    value: float | None
    position: int | None = None
    source: str | None = None
    query_id: str | None = None
    session_id: str | None
    context_json: dict[str, Any] | None = None
    idempotency_key: str | None = None


class InteractionRecord(BaseModel):
    interaction_id: int
    user_id: str
    media_type: str
    media_id: int
    title: str
    event_type: InteractionType
    reaction: str | None
    value: float | None
    position: int | None
    source: str | None
    query_id: str | None
    session_id: str | None
    context_json: dict[str, Any] | None
    idempotency_key: str | None = None
