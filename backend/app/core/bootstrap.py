import time
import os

import nltk
from app.core.config import (
    NLTK_PATH,
    QDRANT_API_KEY,
    QDRANT_ENDPOINT,
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
)
from app.llm.custom_models import (
    load_bm25_files,
    load_cross_encoder,
    load_sentence_model,
    setup_intent_classifier,
)
from app.rec_pipeline.recommend import RecommendPipeline
from app.retrieval.base_retriever import BaseRetriever
from app.retrieval.query_encoder import Encoder
from app.retrieval.vectorstore import connect_qdrant
from app.services.chatbot import build_chat_fn

os.environ["TOKENIZERS_PARALLELISM"] = "false"

start = time.time()

# NLTK, embedding, and reranking models
nltk.data.path.append(NLTK_PATH)
intent_classifier = setup_intent_classifier()
embed_model = load_sentence_model()
bm25_models, bm25_vocabs = load_bm25_files()
query_encoder = Encoder(embed_model, bm25_models, bm25_vocabs)
cross_encoder = load_cross_encoder()

# Vector db client, base retriever
qdrant_client = connect_qdrant(QDRANT_ENDPOINT, QDRANT_API_KEY)
base_ret = BaseRetriever(
    qdrant_client,
    movie_collection=QDRANT_MOVIE_COLLECTION_NAME,
    tv_collection=QDRANT_TV_COLLECTION_NAME,
    dense_vector_name="dense_vector",
    sparse_vector_name="sparse_vector",
)

# Orchestration pipeline
pipeline = RecommendPipeline(base_ret, ce_model=cross_encoder, rrf_k=60)

# Chat entrypoint
chat_fn = build_chat_fn(
    pipeline=pipeline,
    intent_classifier=intent_classifier,
    query_encoder=query_encoder,
)

print(f"🔧 Total startup time: {time.time() - start:.2f}s")
