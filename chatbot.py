from rag_pipeline import MovieRetriever
from llm_utils import embed_text, call_chat_model, build_chat_history
from vectorstore import connect_qdrant
from config import QDRANT_ENDPOINT, QDRANT_API_KEY, QDRANT_COLLECTION_NAME

SYSTEM_PROMPT = """You are a professional film curator and critic. Your role is to analyze the user's preferences and recommend high-quality films using the provided context. 
Focus on: 

- Artistic merit and storytelling, 
- Genres, themes, and tone
- Popularity, IMDB ratings, and Rotten Tomatoes ratings
- Provide a brief explanation of why the user might enjoy each movie. Include IMDB rating, Rotten Tomatoe ratings, and movie poster.

Answer with authority and care, only in English.
"""


def chat(question, history, genres=None, providers=None, year_range=None):
    if not question or question.strip() == "":
        return "What are you in the mood for today? 🎥"
    
    qdrant_client = connect_qdrant(endpoint=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)
    retriever = MovieRetriever(qdrant_client, QDRANT_COLLECTION_NAME)
    
    query_vector = retriever.embed(question, embed_text)
    retrieved_movies = retriever.retrieve(query_vector, genres, providers, year_range)
    context = retriever.format_context(retrieved_movies)

    message_history = build_chat_history (history or [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += message_history
    messages.append({
        "role": "user",
        "content": f"{question}\n\nContext:\nBased on the following retrieved movies, suggest the best recommendations.\n\n{context}"
    })

    print (f"User question: {question}\n\nRetrieved contents:\n {context}") # Debugging line to log the user question and retrieved movies

    return call_chat_model(messages)