import asyncio
from concurrent.futures import ThreadPoolExecutor
from llm_services import embed_text, classify_intent, call_chat_model_openai, call_chat_model_anthropic


def build_chat_fn(retriever):
    def chat(question, history, media_type="movies", genres=None, providers=None, year_range=None, model_provider="openai"):  # Set model_provider="anthropic" if using Anthropic LLM for chat completions. Defaults to "openai".
        with ThreadPoolExecutor() as executor:
                # Classify user intent to determine whether it is a recommendation ask
                intent_future = executor.submit(classify_intent, question)
                
                # Embed user query asynchronously to shorten response time
                query_vector_future = executor.submit(retriever.embed, question, embed_text)
                
                is_rec_intent = intent_future.result()
                query_vector = query_vector_future.result()
    
        if is_rec_intent:
            # If Yes to recomendation intent, proceed with the RAG pipeline for retrieval and recommendation
            retrieved_movies = retriever.retrieve_and_rerank(query_vector, media_type.lower(), genres, providers, year_range)
            context = retriever.format_context(retrieved_movies)
            
            user_message = f"{question}\n\nContext:\nBased on the following retrieved {media_type.lower()}, suggest the best recommendations.\n\n{context}"
        else:
            # If No, proceed with a general conversation
            user_message = question

        # Check which LLM model to use
        if model_provider.lower() == "anthropic":
            for chunk in call_chat_model_anthropic(history, user_message):
                yield chunk
        else:
            for chunk in call_chat_model_openai(history, user_message):
                yield chunk
    return chat