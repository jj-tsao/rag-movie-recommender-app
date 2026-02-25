from __future__ import annotations

import re
from typing import Any


def format_embedding_text(media_type: str, media: dict) -> str:
    """
    Format a media dict into text for dense embedding.
    """
    title = (
        media.get("title" if media_type == "movie" else "name", "Unknown") or "Unknown"
    )
    genres = [genre["name"] for genre in media.get("genres", [""])]
    overview = media.get("overview", "").strip()
    tagline = media.get("tagline", "").strip()
    stars = media.get("stars", [])
    keywords = media.get("keywords", [])

    date_field = "release_date" if media_type == "movie" else "first_air_date"
    release_date = media.get(date_field, "")

    collection_name = (
        media.get("belongs_to_collection", {}).get("name", "")
        if media.get("belongs_to_collection", {})
        else ""
    )
    franchise = f"Franchise: {collection_name}" if collection_name else []

    if media_type == "movie":
        director = media.get("director", "")
        specific_content = f"Director: {director}" if director else []
    else:  # TV show
        creator = media.get("creator", [])
        specific_content = f"Creator: {', '.join(creator)}" if creator else []

    parts = [
        f"Title: {title}",
        f"Genres: {', '.join(genres)}" if genres else [],
        f"Overview: {overview}" if overview else [],
        f"Tagline: {tagline}" if tagline else [],
        franchise or [],
        specific_content or [],
        f"Stars: {', '.join(stars)}" if stars else [],
        f"Release Date: {release_date[:10]}" if release_date else [],
        f"Keywords: {', '.join(keywords)}" if keywords else [],
    ]

    return "\n".join([part for part in parts if part]).strip()


def _truncate_overview(text: str, *, max_sents: int = 2) -> str:
    """Compact overview for LLM prompts (1-2 sentences, hard cap)."""
    text = (text or "").strip()
    if not text:
        return ""

    sents = re.split(r"(?<=[.!?])\s+", text)
    compact = " ".join(sents[:max_sents]).strip() if sents else text

    return compact


def format_llm_context(media_type: str, media: dict) -> dict[str, Any]:
    """Compact, structured LLM card to store in Qdrant payload.

    Short keys reduce token usage when json-dumped:
      t: title
      y: release year (int) or None
      g: genres (<=4)
      k: keywords (<=8)
      o: overview (1 sentence, <=240 chars)
    """
    id = media.get("id", 0)
    title = (
        media.get("title" if media_type == "movie" else "name", "Unknown") or "Unknown"
    )

    genres = [genre["name"] for genre in media.get("genres", [""])]
    overview = _truncate_overview(media.get("overview", "").strip())
    keywords = media.get("keywords", [])[:8]

    return {"id": id, "t": title, "g": genres, "k": keywords, "o": overview}