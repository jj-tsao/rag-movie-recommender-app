import os
import time

import nltk
from app.services.chatbot import build_chat_fn
from app.core.config import (
    NLTK_PATH,
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
)
from app.llm.custom_models import load_sentence_model, load_bm25_files, setup_intent_classifier
from app.retrieval.retriever import get_media_retriever
from app.retrieval.vectorstore import connect_qdrant

start = time.time()
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# nltk.data.path.append(str(NLTK_PATH))


def setup_retriever():
    embed_model = load_sentence_model()
    bm25_models, bm25_vocabs = load_bm25_files()
    nltk.data.path.append(str(NLTK_PATH))
    print("✅ NLTK resources loaded")
    
    qdrant_client = connect_qdrant(endpoint=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)

    return get_media_retriever(
        embed_model=embed_model,
        qdrant_client=qdrant_client,
        bm25_models=bm25_models,
        bm25_vocabs=bm25_vocabs,
        movie_collection_name=QDRANT_MOVIE_COLLECTION_NAME,
        tv_collection_name=QDRANT_TV_COLLECTION_NAME,
    )


# Initialize once at startup
retriever = setup_retriever()
intent_classifier = setup_intent_classifier()
chat_fn = build_chat_fn(retriever, intent_classifier)

print(f"🔧 Total startup time: {time.time() - start:.2f}s")

