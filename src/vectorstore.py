from qdrant_client import QdrantClient


def connect_qdrant(endpoint: str, api_key: str) -> QdrantClient:
    try:
        client = QdrantClient(
            url=endpoint,
            api_key=api_key
        )
        print ("✅ Connected to Qdrant.")
        return client
    except Exception as e:
        print(f"❌ Error connecting to Qdrant: {e}")
        raise
