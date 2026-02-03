"""Shared helpers for discovery endpoints."""

import json
from fastapi import HTTPException
from reelix_agent.core.types import PromptsEnvelope


def sse(event: str, data: dict | str) -> bytes:
    """Format a Server-Sent Event frame."""
    if isinstance(data, dict):
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = data
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


def item_view(c) -> dict:
    """Convert a candidate to a JSON-serializable item view."""
    p = c.payload or {}
    return {
        "id": c.id,
        "media_id": p.get("media_id"),
        "title": p.get("title"),
        "release_year": p.get("release_year"),
        "genres": p.get("genres", []),
        "imdb_rating": p.get("imdb_rating", 0.0),
        "rt_score": p.get("rt_score", "N/A"),
        "poster_url": p.get("poster_url"),
        "backdrop_url": p.get("backdrop_url"),
        "trailer_key": p.get("trailer_key"),
    }


def pick_call(env: PromptsEnvelope, batch: int | None) -> dict:
    """Pick a specific call from the prompts envelope."""
    if not env.calls:
        raise HTTPException(500, "Envelope has no calls")

    call = None
    if batch is not None:
        for c in env.calls:
            if getattr(c, "call_id", None) == batch:
                call = c
                break
        if call is None:
            raise HTTPException(404, f"Batch {batch} not found")
    else:
        call = env.calls[0]

    return {
        "messages": call.messages,
        "items_brief": getattr(call, "items_brief", []),
        "media_id": getattr(call, "media_id", None),
        "batch_id": getattr(call, "call_id", None),
    }