import argparse
import logging

from core.config import OMDB_API_KEY, QDRANT_API_KEY, QDRANT_ENDPOINT
from core.db import get_engine
from core.rating_enrichment import (
    enrich_omdb_rows,
    select_daily_omdb_candidates,
    select_weekly_omdb_candidates,
    sync_imdb_ratings,
    sync_ratings_to_qdrant,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _validate_env():
    missing = []
    if not OMDB_API_KEY:
        missing.append("OMDB_API_KEY")
    if not QDRANT_API_KEY:
        missing.append("QDRANT_API_KEY")
    if not QDRANT_ENDPOINT:
        missing.append("QDRANT_ENDPOINT")
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")


def run_weekly_pipeline(budget: int = 1000, stale_months: int = 6) -> None:
    logger.info("=" * 60)
    logger.info("Starting weekly rating enrichment pipeline")
    logger.info("OMDb budget: %d | Stale threshold: %d months", budget, stale_months)
    logger.info("=" * 60)

    engine = get_engine()

    logger.info("[Step 1/3] Syncing IMDb ratings into media_ratings...")
    sync_imdb_ratings(engine)

    logger.info("[Step 2/3] Enriching with OMDb (RT + Metascore)...")
    rows = select_weekly_omdb_candidates(
        engine, limit=budget, stale_months=stale_months
    )
    enrich_omdb_rows(engine, rows)

    logger.info("[Step 3/3] Syncing ratings to Qdrant...")
    sync_ratings_to_qdrant(engine)

    logger.info("=" * 60)
    logger.info("Weekly rating enrichment pipeline complete!")
    logger.info("=" * 60)


def run_daily_pipeline(
    budget: int = 500, recent_months: int = 3, min_votes: int | None = 200
) -> None:
    logger.info("=" * 60)
    logger.info("Starting daily rating enrichment pipeline")
    logger.info("OMDb budget: %d | Recent window: %d months", budget, recent_months)
    logger.info("=" * 60)

    engine = get_engine()

    logger.info("[Step 1/3] Selecting daily candidates...")
    rows = select_daily_omdb_candidates(
        engine, limit=budget, recent_months=recent_months, min_votes=min_votes
    )

    logger.info("[Step 2/3] Enriching with OMDb...")
    enrich_omdb_rows(engine, rows)

    logger.info("[Step 3/3] Syncing ratings to Qdrant...")
    sync_ratings_to_qdrant(engine)

    logger.info("=" * 60)
    logger.info("Daily rating enrichment pipeline complete!")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Rating enrichment pipeline: IMDb + OMDb → Qdrant"
    )
    parser.add_argument("--mode", required=True, choices=["daily", "weekly"])
    parser.add_argument(
        "--budget",
        type=int,
        default=500,
        help="Max OMDb API calls (free tier = 1,000/day)",
    )
    parser.add_argument(
        "--stale-months",
        type=int,
        default=6,
        help="Weekly: refresh RT scores older than this (months)",
    )
    parser.add_argument(
        "--recent-months",
        type=int,
        default=3,
        help="Daily: only consider titles released within this window (months)",
    )
    args = parser.parse_args()

    _validate_env()

    if args.mode == "daily":
        run_daily_pipeline(budget=args.budget, recent_months=args.recent_months)
    elif args.mode == "weekly":
        run_weekly_pipeline(budget=args.budget, stale_months=args.stale_months)


if __name__ == "__main__":
    main()