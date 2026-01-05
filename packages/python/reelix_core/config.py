from pathlib import Path


QDRANT_MOVIE_COLLECTION_NAME = "Movies_BGE_JAN-AGENT"
QDRANT_TV_COLLECTION_NAME = "TV_Shows_BGE_DEC-AGENT"

INTENT_MODEL = "JJTsao/intent-classifier-distilbert-movierec"  # Fine-tuned intent classification model for query intent classifiation
EMBEDDING_MODEL = "JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5"  # Fine-tuned sentence transfomer model for dense vector embedding
RERANKER_MODEL = "JJTsao/movietv-reranker-cross-encoder-base-v1"
AGENT_MODEL = "gpt-4.1-mini"
CHAT_COMPLETION_MODEL = "gpt-4o-mini"


NLTK_PATH = Path(__file__).resolve().parent.parent / "reelix_models" / "assets" / "nltk_data"
BM25_PATH = Path(__file__).resolve().parent.parent / "reelix_models" / "assets" / "bm25_files"
