from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

from reelix_retrieval.qdrant_filter import provider_ids_from_names
from reelix_agent.core.types import RecQuerySpec

# ---------- Public DTOs (API contract) ----------

ChipGroup = Literal["filters", "vibe", "details"]


class Chip(BaseModel):
    group: ChipGroup
    key: str  # e.g. "providers", "core_genres"
    value: Any  # single value or list; keep JSON-friendly
    label: str | None  # display label
    editable: bool = True  # can user directly add/remove in UI?
    hard: bool = False  # is this a hard constraint vs soft signal?
    source: Literal["user", "llm", "system"] = "llm"  # optional for styling


class PublicActiveSpec(BaseModel):
    # Canonical state the UI should trust (no raw NL query text here)
    media_type: str = "movie"
    providers: list[int] = Field(
        default_factory=list
    )  # provider IDs
    year_range: list[int] = Field(default_factory=lambda: [1970, 2026])

    core_genres: list[str] = Field(default_factory=list)
    exclude_genres: list[str] = Field(default_factory=list)

    core_tone: list[str] = Field(default_factory=list)
    key_themes: list[str] = Field(default_factory=list)
    narrative_shape: list[str] = Field(default_factory=list)

    # Useful but often not primary controls
    sub_genres: list[str] = Field(default_factory=list)


class ActiveSpecEnvelope(BaseModel):
    spec_version: int = 1
    active_spec: PublicActiveSpec
    chips: list[Chip] = Field(default_factory=list)
    # main query_text
    query_text: str | None = None


# ---------- Display helpers ----------
MEDIA_TYPE_LABELS = {"movie": "Movies", "tv": "TV"}


def _titleish(s: str) -> str:
    # cheap prettifier for genre/tone/theme tokens
    return s.replace("_", " ").strip().title()


def _year_label(year_range: list[int]) -> str:
    if len(year_range) != 2:
        return "Year"
    a, b = year_range
    return f"{a}–{b}"


# ---------- Core builder ----------
def craft_active_spec(
    spec: RecQuerySpec,  # your RecQuerySpec instance
    *,
    user_text: str | None = None,
    # Chip display limits (tune freely)
    max_core_genres: int = 3,
    max_tone: int = 3,
    max_themes: int = 3,
    max_narrative: int = 3,
    max_sub_genres: int = 3,
) -> ActiveSpecEnvelope:
    """
    Convert internal RecQuerySpec -> (public active_spec + chip model).
    - Keeps query_text OUT of active_spec.
    - Emits chips with hard/soft + editable guidance for UI.
    """
    # Normalize year_range to list[int]
    providers = provider_ids_from_names(spec.providers)
    yr = list(spec.year_range) if spec.year_range else [1970, datetime.now().year]

    active = PublicActiveSpec(
        media_type=spec.media_type.value,
        providers=providers,
        year_range=yr,
        core_genres=list(getattr(spec, "core_genres", [])),
        sub_genres=list(getattr(spec, "sub_genres", [])),
        exclude_genres=list(getattr(spec, "exclude_genres", [])),
        core_tone=list(getattr(spec, "core_tone", [])),
        narrative_shape=list(getattr(spec, "narrative_shape", [])),
        key_themes=list(getattr(spec, "key_themes", [])),
    )

    chips: list[Chip] = []

    # --- Filters (hard, editable) ---
    # chips.append(
    #     Chip(
    #         group="filters",
    #         key="media_type",
    #         value=active.media_type,
    #         label=MEDIA_TYPE_LABELS.get(
    #             active.media_type, _titleish(active.media_type)
    #         ),
    #         editable=True,
    #         hard=True,
    #         source="system",
    #     )
    # )

    if active.providers:
        chips.append(
            Chip(
                group="filters",
                key="providers",
                value=providers,
                label=None,
                editable=True,
                hard=True,
                source="user",  # treat providers as explicit intent once set
            )
        )

    if active.year_range:
        chips.append(
            Chip(
                group="filters",
                key="year_range",
                value=active.year_range,
                label=str(yr),
                editable=True,
                hard=True,
                source= "system" if yr == [1970, datetime.now().year] else "user",
            )
        )

    # --- Vibe signals (soft; some editable) ---
    # for g in active.core_genres[:max_core_genres]:
    #     chips.append(
    #         Chip(
    #             group="vibe",
    #             key="core_genres",
    #             value=g,
    #             label=_titleish(g),
    #             editable=True,  # editable, but SOFT (hard=False)
    #             hard=False,
    #             source="llm",
    #         )
    #     )

    # for t in active.core_tone[:max_tone]:
    #     chips.append(
    #         Chip(
    #             group="vibe",
    #             key="core_tone",
    #             value=t,
    #             label=_titleish(t),
    #             editable=True,  # often useful to tweak with quick actions
    #             hard=False,
    #             source="llm",
    #         )
    #     )

    # for th in active.key_themes[:max_themes]:
    #     chips.append(
    #         Chip(
    #             group="vibe",
    #             key="key_themes",
    #             value=th,
    #             label=_titleish(th),
    #             editable=False,  # keep themes informational by default
    #             hard=False,
    #             source="llm",
    #         )
    #     )

    # for ns in active.narrative_shape[:max_narrative]:
    #     chips.append(
    #         Chip(
    #             group="vibe",
    #             key="narrative_shape",
    #             value=ns,
    #             label=_titleish(ns),
    #             editable=False,  # often too “model-y” to toggle directly
    #             hard=False,
    #             source="llm",
    #         )
    #     )

    # # --- Details (collapsed area) ---
    # for sg in active.sub_genres[:max_sub_genres]:
    #     chips.append(
    #         Chip(
    #             group="details",
    #             key="sub_genres",
    #             value=sg,
    #             label=_titleish(sg),
    #             editable=False,
    #             hard=False,
    #             source="llm",
    #         )
    #     )

    # Exclusions (if present)
    for eg in active.exclude_genres:
        chips.append(
            Chip(
                group="filters",
                key="exclude_genres",
                value=eg,
                label=f"Not {_titleish(eg)}",
                editable=True,
                hard=True,
                source="user",
            )
        )

    return ActiveSpecEnvelope(active_spec=active, chips=chips, query_text=spec.query_text)
