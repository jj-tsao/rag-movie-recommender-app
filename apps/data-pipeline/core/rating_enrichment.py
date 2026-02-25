import io
import logging
import time
from typing import Mapping, Sequence

import httpx
import pandas as pd
from qdrant_client.http.models import SetPayload, SetPayloadOperation
from core.config import (
    IMDB_RATINGS_URL,
    OMDB_API_KEY,
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
)
from reelix_core.config import (
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
)
from core.vectorstore_pipeline import connect_qdrant
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

OMDB_URL = "https://www.omdbapi.com/"


# == Download IMDb dataset, filter to known titles, upsert into media_ratings ==
def sync_imdb_ratings(engine: Engine) -> None:
    """
    Download IMDb title.ratings.tsv.gz, filter to titles in media_ids, and upsert directly into media_ratings.
    """
    # 1) Fetch the set of known imdb_ids from media_ids
    logger.info("Fetching known IMDb IDs from media_ids...")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT imdb_id FROM media_ids WHERE imdb_id IS NOT NULL")
        ).fetchall()
    known_imdb_ids = {r[0] for r in rows}
    logger.info("Found %d known IMDb IDs in media_ids.", len(known_imdb_ids))

    if not known_imdb_ids:
        logger.warning("No IMDb IDs in media_ids — skipping IMDb sync.")
        return

    # 2) Download full dataset into pandas (pipeline memory)
    logger.info("Downloading IMDb ratings dataset...")
    resp = httpx.get(IMDB_RATINGS_URL, timeout=60)
    resp.raise_for_status()

    df = pd.read_table(
        io.BytesIO(resp.content),
        compression="gzip",
        sep="\t",
        dtype={"tconst": "string", "averageRating": "float32", "numVotes": "int32"},
    )
    logger.info("Loaded %d total IMDb rows into memory.", len(df))

    # 3) Filter to only known titles
    df = df[df["tconst"].isin(known_imdb_ids)].rename(
        columns={"averageRating": "average_rating", "numVotes": "num_votes"}
    )
    logger.info("Filtered to %d rows matching existing media_ids.", len(df))

    if df.empty:
        logger.warning("No matching IMDb ratings found — skipping upsert.")
        return

    # 4) Upsert into media_ratings in chunks
    upsert_sql = text(
        """
        INSERT INTO media_ratings AS mr
            (media_type, tmdb_id, imdb_id, release_date, imdb_rating, imdb_votes, updated_at)
        SELECT
          mi.media_type,
          mi.tmdb_id,
          mi.imdb_id,
          mi.release_date,
          :average_rating,
          :num_votes,
          now()
        FROM media_ids mi
        WHERE mi.imdb_id = :tconst
        ON CONFLICT (media_type, tmdb_id) DO UPDATE
          SET imdb_rating = EXCLUDED.imdb_rating,
              imdb_votes  = EXCLUDED.imdb_votes,
              updated_at  = now()
        WHERE mr.imdb_rating IS DISTINCT FROM EXCLUDED.imdb_rating
           OR mr.imdb_votes  IS DISTINCT FROM EXCLUDED.imdb_votes
        """
    )

    CHUNK = 500
    total = len(df)
    for start in range(0, total, CHUNK):
        chunk = df.iloc[start : start + CHUNK]
        params = chunk[["tconst", "average_rating", "num_votes"]].to_dict("records")
        with engine.begin() as conn:
            conn.execute(upsert_sql, params)
        logger.info(
            "Upserted IMDb chunk %d–%d / %d",
            start + 1,
            min(start + CHUNK, total),
            total,
        )

    logger.info("media_ratings updated with %d IMDb ratings.", total)


# == OMDb for RT, Metacritics, and awards (daily & weekly) ==
def fetch_from_omdb(
    imdb_id: str,
) -> tuple[int | None, int | None, str | None, str]:
    """
    Call OMDb by IMDb ID and extract:
      - Rotten Tomatoes score (0–100) if present
      - Metascore (0–100) if present
      - Awards summary string (may be None)
    Returns:
      (rt_score, metascore, awards_summary, omdb_status)
    where omdb_status ∈ {"ok", "not_found", "error"}.
    """
    params = {"apikey": OMDB_API_KEY, "i": imdb_id}

    try:
        resp = httpx.get(OMDB_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("HTTP error for imdb_id=%s: %s", imdb_id, e)
        return None, None, None, "error"

    if data.get("Response") != "True":
        err = (data.get("Error") or "").lower()
        logger.info("OMDb: no data for %s: %s", imdb_id, data.get("Error"))

        if "not found" in err or "incorrect imdb id" in err:
            return None, None, None, "not_found"

        # Other OMDb-side issues → treat as transient error
        return None, None, None, "error"

    # Rotten Tomatoes
    rt_score: int | None = None
    for rating in data.get("Ratings", []):
        if rating.get("Source") == "Rotten Tomatoes":
            value = rating.get("Value")  # e.g. "87%"
            if value and value.endswith("%"):
                try:
                    rt_score = int(value.rstrip("%"))
                except ValueError:
                    rt_score = None
            break

    # Metascore
    metascore: int | None = None
    metascore_raw = data.get("Metascore")
    if metascore_raw and metascore_raw != "N/A":
        try:
            metascore = int(metascore_raw)
        except ValueError:
            metascore = None

    if metascore is None:
        # Fallback: parse from Ratings array if Metascore field missing
        for rating in data.get("Ratings", []):
            if rating.get("Source") == "Metacritic":
                value = rating.get("Value")  # e.g. "65/100"
                if value and "/" in value:
                    num = value.split("/", 1)[0]
                    try:
                        metascore = int(num)
                    except ValueError:
                        metascore = None
                break

    awards: str | None = data.get("Awards") or None

    return rt_score, metascore, awards, "ok"


def select_daily_omdb_candidates(
    engine: Engine,
    limit: int = 1000,
    recent_months: int = 3,
    min_votes: int | None = 200,
) -> Sequence[Mapping]:
    """
    DAILY selector — focused exclusively on recent releases.

    All tiers are scoped to titles released within `recent_months`.
    Catalog-wide sweeps are left to the weekly pipeline.

    Priority:
      0) Recent + never checked (omdb_status IS NULL)
      1) Recent + error (transient failure, retry after 1 day)
      2) Recent + has RT score (refresh after 7 days)
      3) Recent + not_found (retry after 14 days)
      99) Everything else (skip — weekly handles it)
    """
    vote_filter = ""
    params: dict = {"limit": limit}

    if min_votes is not None:
        vote_filter = "AND (imdb_votes IS NULL OR imdb_votes >= :min_votes)"
        params["min_votes"] = min_votes

    sql = text(
        f"""
        SELECT
            media_type,
            tmdb_id,
            imdb_id,
            imdb_rating,
            imdb_votes,
            rt_score,
            omdb_status,
            omdb_last_checked,
            release_date,
            CASE
              WHEN omdb_status IS NULL
                THEN 0  -- never checked

              WHEN omdb_status = 'error'
                AND (omdb_last_checked IS NULL
                     OR omdb_last_checked < now() - interval '1 day')
                THEN 1  -- transient failure, retry quickly

              WHEN omdb_status = 'ok'
                AND (omdb_last_checked IS NULL
                     OR omdb_last_checked < now() - interval '7 days')
                THEN 2  -- refresh existing scores

              WHEN omdb_status = 'not_found'
                AND (omdb_last_checked IS NULL
                     OR omdb_last_checked < now() - interval '14 days')
                THEN 3  -- worth retrying after 2 weeks

              ELSE 99   -- skip
            END AS priority
        FROM media_ratings
        WHERE imdb_id IS NOT NULL
          AND media_type = 'movie'
          AND release_date >= now() - interval '{recent_months} months'
          {vote_filter}
          AND (
               omdb_status IS NULL
            OR (omdb_status = 'error'
                AND (omdb_last_checked IS NULL
                     OR omdb_last_checked < now() - interval '1 day'))
            OR (omdb_status = 'ok'
                AND (omdb_last_checked IS NULL
                     OR omdb_last_checked < now() - interval '7 days'))
            OR (omdb_status = 'not_found'
                AND (omdb_last_checked IS NULL
                     OR omdb_last_checked < now() - interval '14 days'))
          )
        ORDER BY
          priority ASC,
          release_date DESC,
          imdb_votes DESC NULLS LAST
        LIMIT :limit
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return rows


def select_weekly_omdb_candidates(
    engine: Engine,
    limit: int = 1000,
    stale_months: int = 6,
    min_votes: int | None = None,
) -> Sequence[Mapping]:
    """
    WEEKLY selector: sweep broader catalog with budget-aware prioritization.

    Priority tiers (lower = higher priority):
      0) Never checked (omdb_status IS NULL) — highest value, no data at all
      1) Previously errored (omdb_status = 'error') — transient failure, worth retrying
      2) Has RT score but stale (omdb_last_checked > stale_months) — keep data fresh
      3) not_found but >12 months since last check — low-value retry, OMDb may have added data
      99) Everything else — skip

    Guards:
      - imdb_id IS NOT NULL
      - media_type = 'movie' (OMDb has very limited TV RT coverage)
      - optional imdb_votes >= min_votes
    """
    vote_filter = ""
    params: dict = {"limit": limit}

    if min_votes is not None:
        vote_filter = "AND (imdb_votes IS NULL OR imdb_votes >= :min_votes)"
        params["min_votes"] = min_votes

    sql = text(
        f"""
        SELECT
            media_type,
            tmdb_id,
            imdb_id,
            imdb_rating,
            imdb_votes,
            rt_score,
            omdb_status,
            omdb_last_checked,
            release_date,
            CASE
              WHEN omdb_status IS NULL
                THEN 0  -- never checked

              WHEN omdb_status = 'error'
                THEN 1  -- transient failure, retry

              WHEN rt_score IS NOT NULL
                AND omdb_last_checked < now() - interval '{stale_months} months'
                THEN 2  -- stale RT score, refresh

              WHEN omdb_status = 'not_found'
                AND omdb_last_checked < now() - interval '12 months'
                THEN 3  -- old not_found, worth retrying

              ELSE 99   -- skip
            END AS priority
        FROM media_ratings
        WHERE imdb_id IS NOT NULL
          AND media_type = 'movie'
          {vote_filter}
          AND (
               omdb_status IS NULL
            OR omdb_status = 'error'
            OR (rt_score IS NOT NULL
                AND omdb_last_checked < now() - interval '{stale_months} months')
            OR (omdb_status = 'not_found'
                AND omdb_last_checked < now() - interval '12 months')
          )
        ORDER BY
          priority ASC,
          imdb_votes DESC NULLS LAST,
          release_date DESC
        LIMIT :limit
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    return rows


def enrich_omdb_rows(
    engine: Engine,
    rows: Sequence[Mapping],
    sleep_between: float = 0.3,
    flush_every: int = 50,
) -> None:
    """
    Shared micro-batch OMDb enrichment loop.

    Calls fetch_from_omdb per row and flushes updates to media_ratings
    every `flush_every` calls for crash resilience.
    """
    if not rows:
        logger.info("No candidates require OMDb enrichment.")
        return

    logger.info("Enriching %d candidates via OMDb...", len(rows))

    update_sql = text(
        """
        UPDATE media_ratings
        SET rt_score         = :rt_score,
            omdb_last_checked = now(),
            omdb_status       = :omdb_status,
            metascore         = :metascore,
            awards_summary    = :awards_summary,
            updated_at        = now()
        WHERE tmdb_id   = :tmdb_id
          AND media_type = :media_type
          AND (
               rt_score       IS DISTINCT FROM :rt_score
            OR omdb_status    IS DISTINCT FROM :omdb_status
            OR metascore      IS DISTINCT FROM :metascore
            OR awards_summary IS DISTINCT FROM :awards_summary
          )
        """
    )

    batch_updates: list[dict] = []
    total_processed = 0
    total_flushed = 0
    total_batches = (len(rows) + flush_every - 1) // flush_every

    for idx, row in enumerate(rows, start=1):
        rt_score, metascore, awards, status = fetch_from_omdb(row["imdb_id"])

        batch_updates.append(
            {
                "media_type": row["media_type"],
                "tmdb_id": row["tmdb_id"],
                "rt_score": rt_score,
                "omdb_status": status,
                "metascore": metascore,
                "awards_summary": awards,
            }
        )

        total_processed += 1
        time.sleep(sleep_between)

        # Flush micro-batch to DB
        if len(batch_updates) >= flush_every or idx == len(rows):
            batch_num = (idx + flush_every - 1) // flush_every
            with engine.begin() as conn:
                conn.execute(update_sql, batch_updates)

            total_flushed += len(batch_updates)
            logger.info(
                "Flushed batch %d/%d: %d processed (total: %d/%d)",
                batch_num,
                total_batches,
                len(batch_updates),
                total_flushed,
                len(rows),
            )
            batch_updates = []

    logger.info(
        "OMDb enrichment complete: %d candidates processed.", total_processed
    )


# == Step 4: Sync ratings from media_ratings into Qdrant payload ==
def select_ratings_for_qdrant_sync(
    engine: Engine,
    limit: int = 1000,
) -> Sequence[Mapping]:
    """
    Criteria:
    - Never synced (qdrant_synced_at IS NULL)
    - OR updated since last sync (updated_at > qdrant_synced_at)
    """
    sql = text(
        """
        SELECT media_type,
               tmdb_id,
               imdb_rating,
               imdb_votes,
               rt_score,
               metascore,
               awards_summary,
               updated_at
        FROM media_ratings
        WHERE (qdrant_synced_at IS NULL OR updated_at > qdrant_synced_at)
          AND qdrant_point_missing IS NOT TRUE
          AND media_type = 'movie'
        ORDER BY updated_at ASC
        LIMIT :limit
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(sql, {"limit": limit}).mappings().all()

    return rows


def sync_ratings_to_qdrant(engine: Engine, batch_size: int = 1000) -> None:
    """
    Incrementally sync imdb_rating, imdb_votes, rt_score, metascore, awards_summary
    into Qdrant payload.

    Uses qdrant_synced_at as a watermark so that each row is only sent when it's
    new or changed.

    Three-phase approach per batch:
      1. Batch existence check via client.retrieve() — avoids per-row 404s
      2. Batch payload update via batch_update_points() — reduces HTTP calls
      3. Mark all rows synced (existing + non-existent) in Postgres
    """
    RETRIEVE_CHUNK = 200
    BATCH_UPDATE_CHUNK = 100

    client = connect_qdrant(QDRANT_API_KEY, QDRANT_ENDPOINT)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    collection_map = {
        "movie": QDRANT_MOVIE_COLLECTION_NAME,
        "tv": QDRANT_TV_COLLECTION_NAME,
    }

    update_sql = text(
        """
        UPDATE media_ratings
        SET qdrant_synced_at = :synced_at
        WHERE tmdb_id = :tmdb_id
          AND media_type = :media_type
        """
    )

    batch_count = 0

    while True:
        batch_count += 1
        rows = select_ratings_for_qdrant_sync(engine, limit=batch_size)
        if not rows:
            logger.info("No ratings to sync to Qdrant.")
            break

        logger.info("Qdrant sync batch #%d: %d rows selected", batch_count, len(rows))

        # Group rows by media_type
        rows_by_type: dict[str, list[Mapping]] = {}
        for row in rows:
            rows_by_type.setdefault(row["media_type"], []).append(row)

        for media_type, type_rows in rows_by_type.items():
            collection_name = collection_map.get(media_type)
            if collection_name is None:
                logger.warning(
                    "Skipping %d rows with invalid media_type=%s",
                    len(type_rows),
                    media_type,
                )
                continue

            all_tmdb_ids = [r["tmdb_id"] for r in type_rows]

            # -- Phase 1: Batch existence check --
            existing_ids: set[int] = set()
            for i in range(0, len(all_tmdb_ids), RETRIEVE_CHUNK):
                chunk_ids = all_tmdb_ids[i : i + RETRIEVE_CHUNK]
                try:
                    found = client.retrieve(
                        collection_name=collection_name,
                        ids=chunk_ids,
                        with_payload=False,
                        with_vectors=False,
                    )
                    existing_ids.update(p.id for p in found)
                except Exception:
                    logger.warning(
                        "retrieve() failed for chunk of %d IDs; treating as existing",
                        len(chunk_ids),
                    )
                    existing_ids.update(chunk_ids)

            rows_to_sync = [r for r in type_rows if r["tmdb_id"] in existing_ids]
            rows_to_skip = [r for r in type_rows if r["tmdb_id"] not in existing_ids]

            logger.info(
                "%s: %d in Qdrant, %d not indexed",
                media_type,
                len(rows_to_sync),
                len(rows_to_skip),
            )

            # Flag non-existent rows so they don't clog the sync queue.
            # The indexing pipeline clears qdrant_point_missing after
            # upserting new points, re-queuing them for rating sync.
            if rows_to_skip:
                skip_ids = [r["tmdb_id"] for r in rows_to_skip]
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            UPDATE media_ratings
                            SET qdrant_point_missing = TRUE,
                                qdrant_synced_at = updated_at
                            WHERE media_type = :media_type
                              AND tmdb_id = ANY(:tmdb_ids)
                            """
                        ),
                        {"media_type": media_type, "tmdb_ids": skip_ids},
                    )

            if not rows_to_sync:
                continue

            # -- Phase 2: Batch payload update --
            operations = [
                SetPayloadOperation(
                    set_payload=SetPayload(
                        payload={
                            "imdb_rating": r["imdb_rating"],
                            "imdb_votes": r["imdb_votes"],
                            "rt_score": r["rt_score"],
                            "metascore": r["metascore"],
                            "awards_summary": r["awards_summary"],
                        },
                        points=[r["tmdb_id"]],
                    )
                )
                for r in rows_to_sync
            ]

            # Send in chunks with per-chunk Postgres flush
            synced_count = 0
            total_chunks = (len(operations) + BATCH_UPDATE_CHUNK - 1) // BATCH_UPDATE_CHUNK
            for i in range(0, len(operations), BATCH_UPDATE_CHUNK):
                chunk_ops = operations[i : i + BATCH_UPDATE_CHUNK]
                chunk_rows = rows_to_sync[i : i + BATCH_UPDATE_CHUNK]
                chunk_num = i // BATCH_UPDATE_CHUNK + 1

                try:
                    client.batch_update_points(
                        collection_name=collection_name,
                        update_operations=chunk_ops,
                        wait=True,
                    )
                except Exception:
                    logger.error(
                        "batch_update_points failed for chunk %d/%d (%d ops); will retry next run",
                        chunk_num,
                        total_chunks,
                        len(chunk_ops),
                    )
                    continue

                # -- Phase 3: Mark this chunk as synced --
                chunk_updates = [
                    {
                        "tmdb_id": r["tmdb_id"],
                        "media_type": media_type,
                        "synced_at": r["updated_at"],
                    }
                    for r in chunk_rows
                ]
                with engine.begin() as conn:
                    conn.execute(update_sql, chunk_updates)
                synced_count += len(chunk_updates)

            logger.info(
                "%s: synced %d/%d points to Qdrant in %d calls",
                media_type,
                synced_count,
                len(rows_to_sync),
                total_chunks,
            )

        logger.info("Finished Qdrant sync batch #%d.", batch_count)

    logger.info("Ratings fully synced to Qdrant.")


def clear_qdrant_point_missing(engine: Engine, media_type: str) -> None:
    """
    Blanket reset: clear qdrant_point_missing and re-queue for rating sync.

    Called by the indexing pipeline after upserting points to Qdrant.
    Only touches rows previously flagged as missing — typically a small
    number (~tens) regardless of how many titles were indexed.
    """
    sql = text(
        """
        UPDATE media_ratings
        SET qdrant_point_missing = FALSE,
            qdrant_synced_at = NULL
        WHERE media_type = :media_type
          AND qdrant_point_missing = TRUE
        """
    )

    with engine.begin() as conn:
        result = conn.execute(sql, {"media_type": media_type})
        if result.rowcount:
            logger.info(
                "Re-queued %d previously missing %s titles for Qdrant sync.",
                result.rowcount,
                media_type,
            )
