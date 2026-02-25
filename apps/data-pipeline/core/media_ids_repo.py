from typing import Iterable
from sqlalchemy import text
from sqlalchemy.engine import Engine

def bulk_upsert_media_ids(media_type: str, media_details: Iterable[dict], engine: Engine) -> None:
    """
    Expects each media_detail to have:
      - 'media_type'
      - 'id' (tmdb_id)
      - 'imdb_id' (string or empty string)
      - 'release_date'
    """
    rows = []
    for m in media_details:
        tmdb_id = m.get("id")
        imdb_id = m.get("imdb_id") or None
        release_date = m.get("release_date") or None
        if tmdb_id is None or imdb_id is None:
            continue
        rows.append({"media_type": media_type, "tmdb_id": int(tmdb_id), "imdb_id": imdb_id, "release_date": release_date})

    if not rows:
        return

    sql = text(
        """
        insert into media_ids (media_type, tmdb_id, imdb_id, release_date)
        values (:media_type, :tmdb_id, :imdb_id, :release_date)
        on conflict (media_type, tmdb_id) do update
        set imdb_id      = COALESCE(excluded.imdb_id, media_ids.imdb_id),
            release_date = COALESCE(excluded.release_date, media_ids.release_date);
        """
    )

    with engine.begin() as conn:
        conn.execute(sql, rows)
