import re
import time
from concurrent.futures import ThreadPoolExecutor

from app.llm.llm_completion import call_chat_model_openai
from app.services.usage_logger import log_query_and_results

def sanitize_markdown(md_text: str) -> str:
    return re.sub(r"!\[.*?\]\(.*?\)", "", md_text)


def build_chat_fn(retriever, intent_classifier):
    def chat(
        question,
        history,
        media_type="movie",
        genres=None,
        providers=None,
        year_range=None,
        session_id=None,
        query_id=None,
        device_info=None
    ):
        full_t0 = time.time()

        with ThreadPoolExecutor() as executor:
            # Classify user intent to determine if it is a recommendation ask
            t0 = time.time()
            intent_future = executor.submit(
                lambda q: intent_classifier(q)[0]["label"] == "recommendation", question
            )
            print(f"\n🧠 executor.submit(classify_intent) took {time.time() - t0:.3f}s")

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
            t0 = time.time()
            retrieved_movies, scored_lookup = retriever.retrieve_and_rerank(
                dense_vector,
                sparse_vector,
                media_type.lower(),
                genres,
                providers,
                year_range,
            )
            print(f"\n📚 retrieve_and_rerank() took {time.time() - t0:.3f}s")
            
            query_entry = {
                "query_id": query_id,
                "session_id": session_id,
                "question": question,
                "intent": "recommendation",
                "media_type": media_type,
                "genres": genres,
                "providers": providers,
                "year_start": year_range[0],
                "year_end": year_range[1],
                "device_type": device_info.device_type,
                "platform" : device_info.platform,
                "user_agent": device_info.user_agent
            }
            
            result_entries = []
            for rank, p in enumerate (retrieved_movies):
                s = scored_lookup[p.id]
                result_entries.append({
                    "query_id": query_id,
                    "media_type": media_type,
                    "media_id": p.payload["media_id"],
                    "title": p.payload["title"],
                    "rank": rank + 1,
                    "dense_score": s["dense_score"],
                    "sparse_score": s["sparse_score"],
                    "reranked_score": s["reranked_score"],
                    "is_final_rec": False
                })
                
            try:
                log_query_and_results(query_entry, result_entries)
            except Exception as e:
                print("⚠️ Failed to log to Supabase:", e)

            yield "[[MODE:recommendation]]\n"
            
            context = retriever.format_context(retrieved_movies)
            user_message = f"{question}\n\nContext:\nBased on the following retrieved {media_type.lower()}, suggest the best recommendations.\n\n{context}"

            print(
                f"✨ Total chat() prep time before streaming: {time.time() - full_t0:.3f}s"
            )

            for chunk in call_chat_model_openai(history, user_message):
                yield chunk

        else:
            log_query_and_results(
                query_entry={
                    "query_id": query_id,
                    "session_id": session_id,
                    "question": question,
                    "intent": "chat",
                    "media_type": media_type,
                },
                result_entries=[]
            )
            
            user_message = f"The user did not ask for a recommendation. Ask them to be more specific. Answer this as a general question: {question}"

            print(
                f"✨ Total chat() prep time before streaming: {time.time() - full_t0:.3f}s"
            )
            
            yield "[[MODE:chat]]\n"

            for chunk in call_chat_model_openai(history, user_message):
                yield sanitize_markdown(chunk)

    return chat
