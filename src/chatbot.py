import time
from concurrent.futures import ThreadPoolExecutor

from src.llm_services import call_chat_model_openai, classify_intent


def build_chat_fn(retriever):
    def chat(
        question,
        history,
        media_type="movies",
        genres=None,
        providers=None,
        year_range=None,
    ):
        full_t0 = time.time()
        
        # Check whether user input is empty or whitespace
        if not question.strip():
            emoji = "🎥" if media_type.lower() == "movies" else "📺"
            yield f"Hi there, what are you in the mood for today? {emoji}"
            return

        
        with ThreadPoolExecutor() as executor:
            # Classify user intent to determine if it is a recommendation ask
            t0 = time.time()
            intent_future = executor.submit(classify_intent, question)
            print(f"🧠 executor.submit(classify_intent) took {time.time() - t0:.3f}s")

            # Embed user query as dense vector asynchronously
            t0 = time.time()
            query_vector_future = executor.submit(retriever.embed_dense, question)
            print(f"🧵 executor.submit(embed_text) took {time.time() - t0:.3f}s")

            # Wait for results
            t0 = time.time()
            is_rec_intent = intent_future.result()
            print(f"✅ classify_intent() result received in {time.time() - t0:.3f}s")

            t0 = time.time()
            dense_vector = query_vector_future.result()
            print(f"📈 embed_text() result received in {time.time() - t0:.3f}s")

        # Embed user query as sparse vector for hybrid retrieval
        t0 = time.time()
        sparse_vector = retriever.embed_sparse(question, media_type)
        print(f"📈 embed_sparse() result received in {time.time() - t0:.3f}s")
        
        if is_rec_intent:
            # If Yes, proceed with the RAG pipeline for retrieval and recommendation
            t0 = time.time()            
            retrieved_movies = retriever.retrieve_and_rerank(
                dense_vector,
                sparse_vector,
                media_type.lower(),
                genres,
                providers,
                year_range,
            )
            print(f"📚 retrieve_and_rerank() took {time.time() - t0:.3f}s")
            
            context = retriever.format_context(retrieved_movies)

            user_message = f"{question}\n\nContext:\nBased on the following retrieved {media_type.lower()}, suggest the best recommendations.\n\n{context}"
        else:
            # If No, proceed with a general conversation
            user_message = question
            
        print(f"✨ Total chat() prep time before streaming: {time.time() - full_t0:.3f}s")

        for chunk in call_chat_model_openai(history, user_message):
            yield chunk

    return chat
