from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, PointStruct
from reelix_core.config import QDRANT_MOVIE_COLLECTION_NAME, QDRANT_TV_COLLECTION_NAME
from tqdm import tqdm


def connect_qdrant(api_key: str, endpoint: str) -> QdrantClient:
    try:
        client = QdrantClient(
            url=endpoint,
            api_key=api_key,
        )
        print("✅ Connected to Qdrant.")
        return client
    except Exception as e:
        print(f"❌ Error connecting to Qdrant: {e}")
        raise


def create_qdrant_collection(client: QdrantClient, media_type: str, vector_size: int):
    try:
        collections = client.get_collections().collections
        collection_name = (
            QDRANT_MOVIE_COLLECTION_NAME
            if media_type == "movie"
            else QDRANT_TV_COLLECTION_NAME
        )
        if collection_name in [c.name for c in collections]:
            print(f"👍 Collection '{collection_name}' found.")
            return

        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense_vector": models.VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
            },
            sparse_vectors_config={
                "sparse_vector": models.SparseVectorParams(),
            },
        )
        print(f"✅ Collection '{collection_name}' created.")

        client.create_payload_index(
            collection_name=collection_name,
            field_name="media_id",
            field_schema=models.PayloadSchemaType.INTEGER,
            wait=True,
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="title",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="release_year",
            field_schema=models.PayloadSchemaType.INTEGER,
            wait=True,
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="genres",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="watch_providers",
            field_schema=models.PayloadSchemaType.INTEGER,
            wait=True,
        )

        print("✅ Qdrant index created.")

    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        raise


def safe_upload(client, collection_name, points, retries=3):
    import time

    for attempt in range(1, retries + 1):
        try:
            client.upload_points(
                collection_name=collection_name, points=points, wait=True
            )
            return True
        except Exception as e:
            print(f"⚠️ Upload attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
    return False


RATING_FIELDS = ("imdb_rating", "imdb_votes", "rt_score", "metascore", "awards_summary")


def _preserve_existing_ratings(client, collection_name, points):
    """Fetch rating fields from existing points and merge into new payloads."""
    point_ids = [p.id for p in points]
    try:
        existing = client.retrieve(
            collection_name=collection_name,
            ids=point_ids,
            with_payload=list(RATING_FIELDS),
            with_vectors=False,
        )
    except Exception:
        return

    ratings_by_id = {}
    for p in existing:
        if p.payload:
            ratings = {k: v for k, v in p.payload.items() if v is not None}
            if ratings:
                ratings_by_id[p.id] = ratings

    if not ratings_by_id:
        return

    for point in points:
        existing_ratings = ratings_by_id.get(point.id)
        if existing_ratings:
            point.payload.update(existing_ratings)


def batch_insert_into_qdrant(client, media_type, data, batch_size=100):
    for i in tqdm(range(0, len(data), batch_size), desc="📤 Inserting batches"):
        batch = data[i : i + batch_size]
        collection_name = (
            QDRANT_MOVIE_COLLECTION_NAME
            if media_type == "movie"
            else QDRANT_TV_COLLECTION_NAME
        )
        try:
            points = [
                PointStruct(
                    id=item["payload"]["media_id"],
                    vector={
                        "dense_vector": item["dense_vector"],
                        "sparse_vector": item["sparse_vector"],
                    },
                    payload=item["payload"],
                )
                for item in batch
            ]
            _preserve_existing_ratings(client, collection_name, points)
            success = safe_upload(client, collection_name, points)
            if success:
                print(
                    f"✅ Inserted batch {i // batch_size + 1} with {len(points)} points."
                )
            else:
                print(f"❌ Failed to insert batch {i // batch_size + 1} after retries.")
        except Exception as e:
            print(f"❌ Error preparing batch {i // batch_size + 1}: {e}")
