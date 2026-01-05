from typing import Optional, Tuple, Iterable, Literal
from datetime import datetime
from qdrant_client.models import (
    Filter as QFilter,
    models as qmodels,
    FieldCondition,
    Range,
)

OnUnknown = Literal["raise", "drop", "warn"]


WATCH_PROVIDERS = {
    "Netflix": 8,
    "Hulu": 15,
    "HBO Max": 1899,
    "Disney+": 337,
    "Apple TV+": 350,
    "Amazon Prime Video": 9,
    "Paramount+": 531,
    "Peacock Premium": 386,
    "MGM Plus": 34,
    "Starz": 43,
    "AMC+": 526,
    "Crunchyroll": 283,
    "BritBox": 151,
    "Acorn TV": 87,
    "Criterion Channel": 258,
    "Tubi TV": 73,
    "Pluto TV": 300,
    "The Roku Channel": 207,
}


def build_qfilter(
    exclude_ids: Optional[list[int]] = None,
    genres: Optional[list[str]] = None,
    providers: Optional[list[int]] = None,
    year_range: Optional[Tuple[int, int]] = (1970, datetime.now().year),
    titles: Optional[list[str]] = None,
    release_year: Optional[int] = None,
) -> QFilter:
    must_not = []
    must = []

    if exclude_ids:
        must_not.append(
            FieldCondition(
                key="media_id", match=qmodels.MatchAny(any=list(exclude_ids))
            )
        )

    if genres:
        must.append(
            FieldCondition(key="genres", match=qmodels.MatchAny(any=list(genres)))
        )

    if providers:
        must.append(
            FieldCondition(
                key="watch_providers", match=qmodels.MatchAny(any=list(providers))
            )
        )

    if year_range:
        start, end = year_range
        if start > end:
            start, end = end, start
        must.append(
            FieldCondition(
                key="release_year",
                range=Range(gte=int(start), lte=int(end)),
            )
        )

    if titles:
        must.append(
            FieldCondition(key="title", match=qmodels.MatchAny(any=list(titles)))
        )

    if release_year:
        must.append(
            FieldCondition(
                key="release_year", match=qmodels.MatchValue(value=int(release_year))
            )
        )

    return QFilter(must=must, must_not=must_not or None)


def provider_ids_from_names(
    provider_names: Iterable[str],
    *,
    include_duplicates: bool = False,
    on_unknown: OnUnknown = "warn", # "raise" | "drop" | "warn"
) -> list[int]:
    """
    Convert provider names -> TMDB provider_ids using WATCH_PROVIDERS.
    """

    def norm(s: str) -> str:
        return " ".join(s.strip().lower().split())

    # Canonical lookup (normalized canonical name -> id)
    canonical: dict[str, int] = {
        norm(name): pid for name, pid in WATCH_PROVIDERS.items()
    }

    # Map common variants to canonical keys (unlikely to hapen since orchestrator agent uses enum)
    aliases: dict[str, str] = {
        "max": "hbo max",
        "hbo": "hbo max",
        "disney plus": "disney+",
        "prime": "amazon prime video",
        "prime video": "amazon prime video",
        "amazon prime": "amazon prime video",
        "paramount plus": "paramount+",
        "paramount+": "paramount+",
        "peacock": "peacock premium",
        "mgm+": "mgm plus",
    }

    out: list[int] = []
    seen: set[int] = set()
    unknown: list[str] = []

    for raw in provider_names:
        key = norm(raw)
        key = aliases.get(key, key)

        pid = canonical.get(key)
        if pid is None:
            unknown.append(raw)
            continue

        if include_duplicates or pid not in seen:
            out.append(pid)
            seen.add(pid)

    if unknown:
        if on_unknown == "raise":
            raise ValueError(
                f"Unknown provider name(s): {unknown}. Allowed: {sorted(WATCH_PROVIDERS)}"
            )
        if on_unknown == "warn":
            # TODO replace with logger / ScoreTrace / telemetry
            print(f"[warn] Unknown provider(s) dropped: {unknown}")

    return out