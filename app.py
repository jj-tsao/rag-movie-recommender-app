from vectorstore import connect_qdrant
from rag_pipeline import MovieRetriever
from chatbot import build_chat_fn
from ui import create_interface
from llm_services import load_sentence_model
from config import QDRANT_ENDPOINT, QDRANT_API_KEY, QDRANT_MOVIE_COLLECTION_NAME, QDRANT_TV_COLLECTION_NAME


def main():
    # Eager load embedding model
    model = load_sentence_model()

    # Persistent Qdrant connection and RAG retriever
    qdrant_client = connect_qdrant(endpoint=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)
    retriever = MovieRetriever(qdrant_client, QDRANT_MOVIE_COLLECTION_NAME, QDRANT_TV_COLLECTION_NAME)
    
    # Build chat function with retriever injected
    chat_fn = build_chat_fn(retriever)
    
    # Create and launch UI
    demo = create_interface(chat_fn)
    demo.launch(inbrowser=True, debug=True, share=False)


if __name__ == "__main__":
    main()
