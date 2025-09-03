from app.retrieval.vectorstore import connect_qdrant
from app.core.config import (
    QDRANT_API_KEY,
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
    QDRANT_ENDPOINT,
)
from qdrant_client.http import models
import numpy as np

client = connect_qdrant(QDRANT_ENDPOINT, QDRANT_API_KEY)


def get_pctl(
    field: str, media_type: str = "movie", pctl: float = 99, batch: int = 2048
) -> float:
    selector = models.PayloadSelectorInclude(include=[field])

    offset = None
    vals = []

    while True:
        points, offset = client.scroll(
            collection_name=QDRANT_MOVIE_COLLECTION_NAME
            if media_type == "movie"
            else QDRANT_TV_COLLECTION_NAME,
            with_payload=selector,
            with_vectors=False,
            limit=batch,
            offset=offset,
        )
        if not points:
            break

        for p in points:
            v = p.payload.get(field)
            if isinstance(v, (int, float)):
                vals.append(float(v))

        if offset is None:
            break

    if not vals:
        raise RuntimeError("No numeric popularity values found.")
    return float(np.percentile(vals, pctl))


print(f"P99 Movie Popularity: {get_pctl('popularity', 'movie', 99):.2f}")
print(f"P95 Movie Popularity: {get_pctl('popularity', 'movie', 95):.2f}")
print(f"P99 Movie Rating: {get_pctl('vote_average', 'movie', 99):.2f}")
print(f"P95 Movie Rating: {get_pctl('vote_average', 'movie', 95):.2f}")
print("=====")
print(f"P99 TV Popularity: {get_pctl('popularity', 'tv', 99):.2f}")
print(f"P95 TV Popularity: {get_pctl('popularity', 'tv', 95):.2f}")
print(f"P99 TV Rating: {get_pctl('vote_average', 'tv', 99):.2f}")
print(f"P95 TV Rating: {get_pctl('vote_average', 'tv', 95):.2f}")

# For a quick test run "python -m app.ranking.pctl" from root (backend)
