
from typing import List, Optional, Tuple
from qdrant_client.models import Filter as QFilter, models as qmodels, FieldCondition, Range


def build_qfilter(
    genres: Optional[List[str]] = None,
    providers: Optional[List[str]] = None,
    year_range: Optional[Tuple[int, int]] = None,
) -> Optional[QFilter]:
    must = []

    if genres:
        must.append(
            FieldCondition(
                key="genres",
                match=qmodels.MatchAny(any=list(genres))
            )
        )

    if providers:
        must.append(
            FieldCondition(
                key="watch_providers",
                match=qmodels.MatchAny(any=list(providers))
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

    return QFilter(must=must) if must else None