import argparse
import asyncio

from reelix_core.config import VECTOR_DIM
from reelix_retrieval.text_formatting import format_embedding_text

from core.bm25_utils import fit_and_save_bm25, sync_bm25_to_runtime
from core.config import (
    BM25_DIR,
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
    TMDB_API_KEY,
    build_param,
)
from core.db import get_engine
from core.embedding_pipeline import embed_and_format
from core.media_ids_repo import bulk_upsert_media_ids
from core.rating_enrichment import clear_qdrant_point_missing
from core.tmdb_client import TMDBClient
from core.vectorstore_pipeline import (
    batch_insert_into_qdrant,
    connect_qdrant,
    create_qdrant_collection,
)

MEDIA_COUNT_IN_K = 0.02  # Number of media to fetch in thousands
MAX_CONNECTIONS = 15
TIMEOUT = 10
CHUNK_SIZE = 1000  # Process and upsert in chunks to limit peak memory


def _validate_env():
    missing = []
    if not TMDB_API_KEY:
        missing.append("TMDB_API_KEY")
    if not QDRANT_API_KEY:
        missing.append("QDRANT_API_KEY")
    if not QDRANT_ENDPOINT:
        missing.append("QDRANT_ENDPOINT")
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")


async def main():
    parser = argparse.ArgumentParser(
        description="Full indexing pipeline: TMDB → embed → Qdrant"
    )
    parser.add_argument("--media-type", required=True, choices=["movie", "tv"])
    parser.add_argument(
        "--media-count",
        type=float,
        default=MEDIA_COUNT_IN_K,
        help="Number of media to fetch in thousands",
    )
    args = parser.parse_args()

    _validate_env()

    media_type = args.media_type
    media_count_in_k = args.media_count

    tmdb_client = TMDBClient(
        api_key=TMDB_API_KEY, max_connections=MAX_CONNECTIONS, timeout=TIMEOUT
    )
    qdrant_client = connect_qdrant(api_key=QDRANT_API_KEY, endpoint=QDRANT_ENDPOINT)
    engine = get_engine()
    params = build_param(media_type)

    try:
        # Fetch media IDs and metadata
        media_ids = await tmdb_client.fetch_media_ids_bulk(
            media_type=media_type,
            media_count_in_k=media_count_in_k,
            **params,  # minimum rating & vote_count
        )
        media_details = await tmdb_client.fetch_all_media_details(
            media_type=media_type,
            media_ids=media_ids,
        )

        # Update media_ids mapping (tmdb_id <-> imdb_id) in the postgres db for downstream rating enrichment
        bulk_upsert_media_ids(
            media_type=media_type,
            media_details=media_details,
            engine=engine,
        )

        # Fit BM25 on full corpus
        all_embedding_texts = [
            format_embedding_text(media_type, m) for m in media_details
        ]
        bm25_model, bm25_vocab = fit_and_save_bm25(
            media_type=media_type, corpus=all_embedding_texts, bm25_dir=BM25_DIR
        )

        # Ensure Qdrant collection exists
        create_qdrant_collection(qdrant_client, media_type, VECTOR_DIM)

        # Embed, format, and upsert in chunks to limit peak memory
        total = len(media_details)
        for i in range(0, total, CHUNK_SIZE):
            chunk_details = media_details[i : i + CHUNK_SIZE]
            chunk_texts = all_embedding_texts[i : i + CHUNK_SIZE]
            chunk_num = i // CHUNK_SIZE + 1
            print(f"\n--- Chunk {chunk_num} ({len(chunk_details)}/{total} items) ---")

            embeddings_and_payload = await embed_and_format(
                media_type=media_type,
                media_details=chunk_details,
                embedding_texts=chunk_texts,
                bm25_model=bm25_model,
                bm25_vocab=bm25_vocab,
            )
            batch_insert_into_qdrant(qdrant_client, media_type, embeddings_and_payload)

        # Re-queue any titles previously flagged as missing from Qdrant. Only touches the small set of rows with qdrant_point_missing=TRUE.
        clear_qdrant_point_missing(engine, media_type)

        # Sync validated BM25 files to runtime assets (backup + atomic copy)
        sync_bm25_to_runtime(media_type=media_type, pipeline_dir=BM25_DIR)

    finally:
        await tmdb_client.aclose()
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
