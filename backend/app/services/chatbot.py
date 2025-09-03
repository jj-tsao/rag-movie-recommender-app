import time
from app.llm.llm_completion import call_chat_model_openai
from app.services.usage_logger import log_query_and_results

def format_context(candidates: list[dict]) -> str:
    # Formart the retrieved documents as context for LLM
    return "\n\n".join(
        [f"  {c.payload.get('llm_context', '')}" for c in candidates]
    )

def build_chat_fn(pipeline, intent_classifier, query_encoder):
    def chat(
        question,
        history,
        media_type="movie",
        genres=None,
        providers=None,
        year_range=None,
        session_id=None,
        query_id=None,
        device_info=None,
        logging=False,
    ):
        full_t0 = time.time()

        # Classify intent
        t0 = time.time()
        is_rec_intent = True
        try:
            is_rec_intent = intent_classifier(question)
        except Exception as e:
            print("⚠️ Intent classifier error; defaulting to recommendation:", e)
        print(f"\n🧠 Intent classification took {time.time() - t0:.3f}s")

        if is_rec_intent:
            t0 = time.time()
            # 1) embed + sparse (async)
            t0 = time.time()
            dense_vec, sparse_vec = query_encoder.dense_and_sparse(question, media_type)
            print(f"📍 Dense/sparse embedding took {time.time() - t0:.3f}s")
            
            # 2) pipeline
            t0 = time.time()
            final_candidates, traces = pipeline.run(
                query_text=question,
                dense_vec=dense_vec.tolist() if hasattr(dense_vec, "tolist") else list(dense_vec),
                sparse_vec=sparse_vec,
                media_type=media_type.lower(),
                genres=genres,
                providers=providers,
                year_range=year_range,
                dense_depth=300,
                sparse_depth=20,
                meta_top_n=100,
                meta_ce_top_n=30,
                weights = dict(dense=0.60, sparse=0.10, rating=0.20, popularity=0.10),
                final_top_k=20,
            )
            print(f"🎬 Recommendation pipeline took {time.time() - t0:.3f}s")
            
            # 3) logging rows (one per candidate) — extend your Supabase schema to include new fields if needed
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
            for rank, c in enumerate (final_candidates):
                result_entries.append({
                    "query_id": query_id,
                    "media_type": media_type,
                    "media_id": c.id,
                    "title": c.payload.get("title"),
                    "rank": rank + 1,
                    "dense_score": c.dense_score,
                    "sparse_score": c.sparse_score,
                    "reranked_score": traces[c.id].final_rrf,
                    "is_final_rec": False
                })
            
            if logging:
                try:
                    log_query_and_results(query_entry, result_entries)
                except Exception as e:
                    print("⚠️ Failed to log query and entries:", e)

            # 4) build LLM context
            system_hint = "[[MODE:recommendation]]\n"
            yield system_hint

            # 5) stream model output
            context = "\n\n".join([c.payload.get("llm_context", "") for c in final_candidates])
            user_message = f"Here are the candidate items:\n{context}\n\nUser query: {question}"
            print(f"✨ Total chat() prep time before streaming: {time.time() - full_t0:.3f}s")
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
            # Non-recommendation: answer directly
            user_message = f"The user did not ask for recommendations. Ask them to be more specific. Answer concisely as a general question: {question}"
            print(f"✨ Total chat() prep time before streaming: {time.time() - full_t0:.3f}s")
            yield "[[MODE:chat]]\n"
            for chunk in call_chat_model_openai(history, user_message):
                yield chunk

    return chat
