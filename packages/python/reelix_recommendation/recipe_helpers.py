import re
from typing import Iterable, List
from qdrant_client.models import Filter as QFilter
from reelix_core.types import QueryFilter, UserTasteContext
from reelix_retrieval.qdrant_filter import build_qfilter


def build_filter(query_filter: QueryFilter | None = None) -> QFilter:
    if query_filter:
        qfilter = build_qfilter(
            genres=query_filter.genres,
            providers=query_filter.providers,
            year_range=query_filter.year_range,
        )
    else:
        qfilter = build_qfilter()
    return qfilter


def build_discover_filter(user_context: UserTasteContext, query_filter: QueryFilter) -> QFilter:
    exclude_ids = user_context.signals.exclude_media_ids

    return build_qfilter(
        exclude_ids=exclude_ids if exclude_ids else [],
        genres=query_filter.genres,
        providers=query_filter.providers,
        year_range=query_filter.year_range,    
    )


def build_bm25_query(
    genres_include: Iterable[str],
    keywords_include: Iterable[str],
    *,
    boost_keywords: int = 2,
) -> str:
    def _clean(s: str) -> str:
        s = s.strip().lower()
        s = s.replace("-", " ")
        s = re.sub(r"\s+", " ", s)
        return s

    # 1) normalize + de-dupe
    gen = sorted({_clean(g) for g in genres_include or [] if g and g.strip()})
    kws = sorted({_clean(k) for k in keywords_include or [] if k and k.strip()})

    # 2) gentle boosting (dup up to tf_clip=3 total occurrences)
    boosted_keywords = []
    for k in kws:
        # ensure at most 3 total repeats later; keep this modest
        boosted_keywords.extend([k] * max(1, min(boost_keywords, 2)))

    # 4) assemble — just a space-separated string (your tokenizer lowercases,
    # strips punctuation, removes stopwords, and Porter-stems later). :contentReference[oaicite:5]{index=5}
    bag: List[str] = []
    bag.extend(gen)  # genres once each
    bag.extend(boosted_keywords)  # keywords (lightly boosted + expanded)

    return " ".join(bag).strip()
