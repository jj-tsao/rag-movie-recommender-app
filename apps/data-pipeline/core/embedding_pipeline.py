import asyncio
import os
from datetime import datetime

from sentence_transformers import SentenceTransformer

from core.bm25_utils import create_bm25_sparse_vector
from reelix_core.config import EMBEDDING_MODEL as EMBEDDING_MODEL_NAME
from reelix_retrieval.text_formatting import format_embedding_text, format_llm_context

sentence_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
print(f"Embedding Model '{EMBEDDING_MODEL_NAME}' loaded.")


async def embed_texts(texts: list[str]):
    batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    embeddings = await asyncio.to_thread(
        sentence_model.encode,
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return embeddings


async def embed_and_format(
    media_type: str,
    media_details: list[dict],
    embedding_texts: list[str],
    bm25_model,
    bm25_vocab: dict,
) -> list[dict]:
    formatted_media = []
    payloads = []

    print(
        f"✨ Formatting and embedding {len(media_details)} {media_type.upper()} items..."
    )

    for embedding_text, media in zip(embedding_texts, media_details):
        # Format paylaod
        # full_text = format_full_doc(media_type, media)
        agent_context = format_llm_context(media_type, media)
        date_field = "release_date" if media_type == "movie" else "first_air_date"

        try:
            raw_date = media.get(date_field, "")
            dt = datetime.strptime(raw_date, "%Y-%m-%d")
            release_date = dt.replace(hour=0, minute=0, second=0).isoformat() + "Z"
            release_year = dt.year
        except (ValueError, TypeError):
            release_date = None
            release_year = None

        metadata = {
            "media_id": media.get("id", 0),
            "media_type": media_type,
            "title": media.get("title" if media_type == "movie" else "name", "Unknown"),
            "genres": [g["name"] for g in media.get("genres", [])],
            "overview": media.get("overview", ""),
            "stars": media.get("stars", []),
            "release_date": release_date,
            "release_year": release_year,
            "keywords": media.get("keywords", []),
            "watch_providers": media.get("providers", []),
            "poster_url": f"https://image.tmdb.org/t/p/w500{media['poster_path']}"
            if media.get("poster_path")
            else "",
            "backdrop_url": f"https://image.tmdb.org/t/p/w500{media['backdrop_path']}"
            if media.get("backdrop_path")
            else "",
            "trailer_key": media.get("trailer_key", ""),
            "popularity": media.get("popularity", 0),
            "vote_average": media.get("vote_average", 0),
            "vote_count": media.get("vote_count", 0),
            "imdb_id": media.get("imdb_id", ""),
            "embedding_text": embedding_text,
            # "llm_context": full_text,
            "llm_context": agent_context,
        }

        if media_type == "movie":
            metadata.update(
                {
                    "collection": media.get("belongs_to_collection", {}).get("name", "")
                    if media.get("belongs_to_collection")
                    else "",
                    "director": media.get("director", "Unknown"),
                }
            )
        else:
            metadata.update(
                {
                    "creator": media.get("creator", []),
                    "season_count": media.get("number_of_seasons"),
                }
            )

        payloads.append(metadata)

    # Compute dense embeddings and BM25 sparse vectors in parallel
    def _compute_all_sparse(texts, vocab, model):
        return [create_bm25_sparse_vector(t, vocab, model) for t in texts]

    embeddings, sparse_vectors = await asyncio.gather(
        embed_texts(embedding_texts),
        asyncio.to_thread(_compute_all_sparse, embedding_texts, bm25_vocab, bm25_model),
    )

    for payload, sparse_vector, embedding in zip(payloads, sparse_vectors, embeddings):
        formatted_media.append(
            {
                "payload": payload,
                "dense_vector": embedding,
                "sparse_vector": sparse_vector,
            }
        )

    return formatted_media
