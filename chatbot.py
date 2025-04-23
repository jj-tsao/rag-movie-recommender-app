from rag_pipeline import MovieRetriever
from llm_utils import embed_text, classify_intent, call_chat_model_openai, call_chat_model_anthropic
from vectorstore import connect_qdrant
from config import QDRANT_ENDPOINT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME


def chat(question, history, genres=None, providers=None, year_range=None, model_provider="openai"):  # Set model_provider="anthropic" f using Anthropic LLM for chat completions. Defaults to "openai".
    # Check if the user input is empty
    if not question or question.strip() == "":
        return "Hi there! What are you in the mood for today? 🎥"
    
    # Classify whether the user input is a recommendation request
    if classify_intent(question):
        # If Yes, proceed with the RAG pipeline for retrieval and response
        qdrant_client = connect_qdrant(endpoint=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)
        retriever = MovieRetriever(qdrant_client, QDRANT_COLLECTION_NAME)
        
        query_vector = retriever.embed(question, embed_text)
        retrieved_movies = retriever.retrieve_and_rerank(query_vector, genres, providers, year_range)
        context = retriever.format_context(retrieved_movies)
        
        user_message = f"{question}\n\nContext:\nBased on the following retrieved movies, suggest the best recommendations.\n\n{context}"
    else:
        # If No, proceed with generic chat without retrieval
        user_message = question
    
    # Choose model provider based on parameter
    if model_provider.lower() == "anthropic":
        return call_chat_model_anthropic(history, user_message)
    else:
        return call_chat_model_openai(history, user_message)
    
