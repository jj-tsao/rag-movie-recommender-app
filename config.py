from dotenv import load_dotenv
import os

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_ENDPOINT = os.getenv("QDRANT_ENDPOINT")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")

if not OPENAI_API_KEY or not QDRANT_API_KEY:
    raise ValueError("Missing API key(s).")
if not QDRANT_ENDPOINT or not QDRANT_COLLECTION_NAME:
    raise ValueError("Missing QDrant URL or collection name.")
