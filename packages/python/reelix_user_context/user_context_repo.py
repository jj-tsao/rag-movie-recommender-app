from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from anyio import to_thread
from reelix_core.types import Interaction, MediaType, UserSignals, UserTasteContext

TABLE_PREFS = "user_preferences"
TABLE_INTERACTIONS = "user_interactions"
TABLE_TASTE = "user_taste_profile"
TABLE_SUBS = "user_subscriptions"
TABLE_SETTINGS = "user_settings"
_TASTE_SIGNAL_EVENTS = {"rec_reaction", "rating", "add_to_watchlist", "remove_from_watchlist", "trailer_view", "love", "like", "dislike"}
_SUPRESS_EVENTS = {"rec_reaction", "rating", "love", "like", "dislike"}


def _ensure_ts(value) -> datetime | None:
    """Normalize timestamps coming from Postgres/Supabase into tz-aware datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Supabase returns ISO strings that may end with `Z`; make them explicit UTC.
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


class SupabaseUserContextRepo:
    def __init__(self, client):
        self.client = client

    # ---------- Async facade ----------
    async def fetch_user_signals(
        self, user_id: str, media_type: MediaType
    ) -> UserSignals:
        return await to_thread.run_sync(
            self._fetch_user_signals_sync, user_id, media_type
        )

    async def fetch_user_taste_context(
        self, user_id: str, media_type: MediaType
    ) -> UserTasteContext:
        return await to_thread.run_sync(
            self._fetch_user_taste_context_sync, user_id, media_type
        )

    # ---------- Private sync impls ----------

    # recent rating event helpers
    def _within(self, ts, *, hours: int) -> bool:
        return ts and ts >= (datetime.now(timezone.utc) - timedelta(hours=hours))

    def _build_exclusions_from_signals(
        self, interactions, cooldown_hours: int = 48
    ) -> list[int]:
        ids = {
            i.media_id
            for i in interactions
            if i.kind in _SUPRESS_EVENTS and self._within(i.ts, hours=cooldown_hours)
        }
        return list(ids)

    def _fetch_user_signals_sync(
        self,
        user_id: str,
        media_type: MediaType,
        interaction_limit: int = 500,
    ) -> UserSignals:
        try:
            pref_res = (
                self.client.table(TABLE_PREFS)
                .select("genres_include, keywords_include")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            pref_rows = getattr(pref_res, "data", None) or []
            prefs = pref_rows[0] if pref_rows else {}
        except Exception:
            prefs = {}

        try:
            q = (
                self.client.table(TABLE_INTERACTIONS)
                .select("media_type, media_id, title, event_type, reaction, value, occurred_at")
                .eq("user_id", user_id)
                .in_("event_type", list(_TASTE_SIGNAL_EVENTS))
            )
            if media_type:
                q = q.eq("media_type", media_type.value)
            inter_res = (
                q.order("occurred_at", desc=True).limit(interaction_limit).execute()
            )
            rows = list(getattr(inter_res, "data", None) or [])
        except Exception:
            rows = []

        interactions = [
            Interaction(
                media_type=str(row["media_type"]),
                media_id=int(row["media_id"]),
                title=str(row["title"]),
                kind=row["event_type"],
                reaction=row["reaction"],
                value=row["value"],
                ts=ts,
            )
            for row in rows
            if (ts := _ensure_ts(row.get("occurred_at") or row.get("created_at")))
            is not None
        ]

        exclude_media_ids = self._build_exclusions_from_signals(
            interactions, cooldown_hours=48
        )

        return UserSignals(
            user_id=user_id,
            genres_include=list(prefs.get("genres_include") or []),
            keywords_include=list(prefs.get("keywords_include") or []),
            interactions=interactions,
            exclude_media_ids=exclude_media_ids,
        )

    def _fetch_user_taste_context_sync(
        self,
        user_id: str,
        media_type: MediaType,
    ) -> UserTasteContext:
        try:
            taste_res = (
                self.client.table(TABLE_TASTE)
                .select("dense, positive_n, negative_n, last_built_at")
                .eq("user_id", user_id)
                .eq("media_type", media_type.value)
                .order("last_built_at", desc=True)
                .limit(1)
                .execute()
            )
            taste_data = getattr(taste_res, "data", None) or []
            taste_row = (
                taste_data
                if isinstance(taste_data, dict)
                else (taste_data[0] if taste_data else None)
            )
        except Exception:
            taste_row = None

        # 2) Signals
        signals = self._fetch_user_signals_sync(user_id, media_type=media_type)

        # 3) Subs + settings
        try:
            subs_res = (
                self.client.table(TABLE_SUBS)
                .select("provider_id")
                .eq("user_id", user_id)
                .eq("active", True)
                .execute()
            )
            subs_rows = getattr(subs_res, "data", None) or []
        except Exception:
            subs_rows = []

        try:
            settings_res = (
                self.client.table(TABLE_SETTINGS)
                .select("provider_filter_mode")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            settings_rows = getattr(settings_res, "data", None) or []
            settings_row = settings_rows[0] if settings_rows else {}
        except Exception:
            settings_row = {}

        # 4) Parse vector + counts
        dense = (taste_row or {}).get("dense") if taste_row else None
        taste_vector: list[float] | None = None
        if isinstance(dense, list):
            taste_vector = [float(v) for v in dense]
        elif isinstance(dense, str):
            raw = dense.strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                trimmed = raw.strip("{}")
                items = [i for i in trimmed.split(",") if i]
                try:
                    parsed = [float(i) for i in items]
                except ValueError:
                    parsed = None
            if isinstance(parsed, list):
                taste_vector = [float(v) for v in parsed]

        def _toi(x):
            return int(x) if x is not None else None

        positive_n = _toi((taste_row or {}).get("positive_n") if taste_row else None)
        negative_n = _toi((taste_row or {}).get("negative_n") if taste_row else None)

        return UserTasteContext(
            signals=signals,
            taste_vector=taste_vector,
            positive_n=positive_n,
            negative_n=negative_n,
            last_built_at=_ensure_ts((taste_row or {}).get("last_built_at"))
            if taste_row
            else None,
            active_subscriptions=[
                int(r["provider_id"])
                for r in subs_rows
                if r.get("provider_id") is not None
            ],
            provider_filter_mode=settings_row.get("provider_filter_mode") or "ALL",
        )
