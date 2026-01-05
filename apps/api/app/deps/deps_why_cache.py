from app.infrastructure.cache.why_cache import WhyCache
from fastapi import Request


def get_why_cache(request: Request) -> WhyCache:
    # type: ignore[attr-defined]
    return request.app.state.why_cache  # type: ignore[attr-defined]
