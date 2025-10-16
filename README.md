# 🎬 Reelix AI – Personalized Movie & TV Show Discovery

**Reelix** is an AI-native discovery agent that understands *vibes* and turns them into cinematic picks.

[![Netlify](https://img.shields.io/badge/Live%20Site-Netlify-42b883?logo=netlify)](https://reelixai.netlify.app/)
[![Retriever Model](https://img.shields.io/badge/Retriever%20Model-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)
[![Intent Classifier](https://img.shields.io/badge/Intent%20Classifier-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/intent-classifier-distilbert-moviebot)
[![CE Reranker](https://img.shields.io/badge/CE%20Reranker-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/movietv-reranker-cross-encoder-base-v1)
[![Made with FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://jjtsao-rag-movie-api.hf.space/docs#/)
[![Built with React](https://img.shields.io/badge/Frontend-React-61dafb?logo=react)](https://reelixai.netlify.app/)
![License](https://img.shields.io/github/license/jj-tsao/rag-movie-recommender-app)

---

Reelix finds your next favorite movies/shows by learning your **personal taste** and the **vibes** you want (themes, tone, pacing, genres).

Under the hood, it combines:

- **Taste vector (SentenceTransformers)** to model what you like (and don’t)
- **Hybrid retrieval (dense embeddings + BM25)** to surface high-signal candidates
- **Metadata-aware reranking** (quality, popularity, genre overlap, recency)
- **Cross-Encoder reranker** for precise final ordering
- **LLM “why you’ll enjoy it”** rationales, streamed via **SSE** to the UI

The result is a fast, **personal For-You recommendation feed** and a flexible **“Explore by Vibe”** experience that adapts as you give feedback.

👉 Try our **Live Product** here: [**Reelix AI**](https://reelixai.netlify.app/)

---
## ✨ Core Experiences

- **Taste Onboarding (`/taste`)** — Quickly signal your preferences (genre/vibe picks; Love / Like / Dislike; trailer views). We build and store a taste vector that refines as you give more feedback.
- **For-You Feed (`/discover`)** — A personalized grid of picks. Each card streams a short rationale and a markdown-rich movie/TV card.
- **Explore by Vibe (`/query`)** — Type “psychological thrillers with a satirical tone,” or tap example chips to see vibe-specific recommendations. Add filters for year range, genres, and streaming services.

### Quick Look

> Reelix understands your vibe and curates markdown-rich suggestions, trailers, and rationale in real time.

<img src="https://github.com/user-attachments/assets/ef03a55a-b9b5-4136-8654-5d7fa3f4e97d" alt="Reelix Preview" width="100%" />


---

## 🧠 How It Works (At a Glance)

```
Taste Signals ──▶ Taste Vector ────┐
                                   │
                                   ▼
User Query ──▶ Dense + BM25 ──▶ Candidate Pool (RRF#1) ──▶ Metadata Rerank ──▶ CE Rerank ──▶ Final Fusion (RRF#2) ──▶ LLM "Why" ──▶ Log final recs
                                   ▲                                                             │                     │
                                   │                                                             ▼                     ▼
                            Filters (Streaming services/genres/year)                     JSON response to UI       SSE stream to UI
```

- **Dense**: fine‑tuned `bge-base-en-v1.5` embeddings
- **Sparse**: BM25 with tokenization/stop‑word cleanup
- **Reranking**: weighted blend of semantic + sparse + quality + popularity (+ optional genre overlap)
- **CE**: `BERT` Cross‑Encoder pairwise reranker
- **Streaming**: reasons & markdown are delivered as **newline-delimited JSON over SSE**.
- **Bootstrap & Lifespan**: loads intent classifier, embedder, BM25, CE reranker, Qdrant client, and configures ticket store.
- **Orchestrator**: Recipes (`interactive`, `for_you_feed`) define inputs (query vs taste), retrieval params, and LLM prompt envelopes.

---

## 🌐 Key API Endpoints

### 1) Taste Onboarding (`/taste`)
Build and maintain a personalized **taste vector** from your interactions and preferences. Stores profile state in Supabase and powers the For-You feed and Vibe Query ranking.

1) `POST /taste_profile/rebuild`
   - Aggregates **user signals**: recent interactions (e.g., Love / Like / Not for me, trailer views), selected genres/vibes, and any provider filters.
   - Fetches the corresponding **item embeddings** from Qdrant and computes a **taste vector** (weighted aggregation + normalization).
   - **Upserts** the profile into Supabase, recording metadata such as `vector_dim`, `n_signals_used`, `build_version`, and timestamps.

3) `GET /taste_profile/me`
   - Returns the latest **profile metadata** and a safe subset of fields for inspection.
   - Useful for gating UX (“has profile been built?”) and for debugging profile freshness across sessions.
   
Under the hood, the rebuild process fetches user signals, loads item embeddings from Qdrant, and calls `build_taste_vector(...)`, then upserts the profile.

### 2) For-You Feed (`/discover`)
Your **For-You** page streams personalized reasons (and a markdown-rich movie/TV profile) per item in real time. Uses a **ticket store** (keyed by `query_id`) with **idle** and **absolute** TTLs to bound prompt/candidate lifespan and prevent stale cross-user access.

1) `POST /discovery/for-you`
   - Queries the user’s taste profile from the database.
   - Runs the **for_you_feed** recipe (dense + BM25 + metadata + CE reranker) against the **user taste context** to fetch **Top-K** candidates.
   - Builds the LLM prompt with those candidates and **persists it in the ticket store** (keyed by `query_id`).
   - Returns the candidate list with metadata (year, genres, posters, trailers, etc.) **plus** a `stream_url` for reasons.
   - Logs a **query-intake record** and a **Top-K candidate snapshot** (IDs, ranks, and **per-signal score traces**) to the database.

3) `GET /discovery/for-you/why?query_id=...` (SSE)
   - Reads the LLM prompt and Top-K candidates from the ticket store.
   - Performs LLM reasoning to generate concise “why you might enjoy it” copy.
   - Streams events `{started, why_delta, done}` where `why_delta` includes `media_id`, optional `imdb_rating` and `rotten_tomatoes_rating`, and `why_you_might_enjoy_it` (markdown).

5) `POST /discovery/log/final_recs`
   - Client posts the final chosen items **and** reasoning (after streaming completes).
   - Upserts existing rows with `stage="final"` and the `why_summary`.

### 3) Vibe Query (`/query`)
Uses a **single streaming endpoint**, with a shared **ticket store** (keyed by `query_id`) and **idle/absolute TTLs** to bound prompt/candidate lifespan and prevent stale cross-user access.

1) `POST /recommendations/interactive`
   - Runs the **interactive** recipe (dense + BM25 + metadata + CE reranker) against the user's **text query** and **taste context** to fetch **Top-K** candidates.
   - Builds the LLM prompt with those candidates and performs LLM reasoning to generate concise “why you might enjoy it” copy.
   - **Streams** the final recommendations **and** their “why” write-ups directly as the response body (text stream).
   - Logs a **query-intake record** and a **Top-K candidate snapshot** (IDs, ranks, and **per-signal score traces**) to the database.

3) `POST /recommend/log/final_recs`
   - Client posts the final chosen items **and** reasoning (after streaming completes).
   - Upserts existing rows with `stage="final"` and the `why_summary`.

### **Frontend details**
- `/discover` loads a grid of picks, then begins SSE streaming of “why” and ratings, updating each card live.
- Users can **Love / Like / Not for me** or **watch trailer**; feedback is logged and triggers controlled taste rebuilds.
- **Smart rebuild controller**: after any rating, start/refresh a 10s timer; if ≥2 ratings when the timer fires, rebuild—**max 1 rebuild per 2 minutes**; queue one pending rebuild during cooldown.

---
## 🏗️ Recommendation Pipeline Architecture (High‑Level)

```
User prompt ──▶ Intent Classifier ──┐
                                    │ yes
                                    ▼
                            Query Encoder (dense + sparse)
                                    │
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
           Sparse Search                         Dense Search
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    │           
                                    ▼           
                 RRF #1: Candidate Pool (dense ⊕ sparse)
                                    │
                                    ▼
                        Metadata Rerank (top 100)
                                    │
                                    │                           (tap from DENSE top-30)
                                    │                                      │
                                    ▼                                      ▼
                             Metadata Top-30                      Cross-Encoder Rerank
                                    │                              (on dense top-30)
                                    │                                      │
                                    └───────────────────┬──────────────────┘
                                                        ▼
                                    RRF #2: Final Fusion (metadata-top ⊕ CE-top)
                                                        │
                                                        ▼
                                                   Top-K to LLM
                                                        ▼
                                                  UI (streaming)

```

**Tunable knobs** (with sensible defaults):

- Retrieval depths: `dense_depth=300`, `sparse_depth=20`
- Fusion: `rrf_k=60`
- Metadata weights: `{dense: 0.60, sparse: 0.15, rating: 0.15, popularity: 0.10}`
- CE window: `meta_ce_top_n=30`
- Final size: `final_top_k=20`

---
## 🚀 Tech Stack

| Layer        | Tech                     |
|-------------|--------------------------|
| Frontend               | React + Vite + Tailwind CSS + ShadCN UI              |
| Backend                | FastAPI (Python) + Docker                            |
| Embedding/ Retrieval   | SentenceTransformers (fine-tuned `bge-base-en-v1.5`) + BM25 |
| Reranking              | **Cross‑Encoder (fine-tuned `bert-base-uncased`)** + Metadata + **RRF** |
| Intent Classification  | DistilBERT (fine-tuned `distilbert-base-uncased`)    |
| Sparse Search          | BM25 (Best Match 25) via `rank_bm25`                 |
| Tokenization           | NLTK (Natural Language Toolkit)                      |
| Vector DB              | Qdrant (hybrid search)                               |
| Storage                | Supabase (profiles, interactions, logs)              |
| Ticket Store           | In-memory or Redis (gzip)                            |
| Chat Completion        | OpenAI API (streamed JSONL/SSE)                      |
| Movie Metadata         | TMDB (The Movie Database) API                        |
| Model Hosting          | Hugging Face Hub                                     |
| Deployment             | Frontend: Netlify, Backend: Hugging Face Spaces      |

---

## 📚 Sample Query Flow

1. User enters a vibe-based prompt (e.g., _“Mind-bending sci-fi with existential themes”_)
2. User selects advanced filters if desired (optional)
3. Intent classifier routes to recommendation (as opposed to general chat)
4. Query is embedded (dense + sparse)
5. Qdrant retrieves top-300 matches via dense and sparse vector search
6. Retrieved titles are reranked by semantic, sparse, rating, popularity, and recency
7. Top-20 reranked results are sent to the LLM for final selection and summary
8. UI streams cards with poster, rating, metadata, rationale, and trailer link
9. Final selections are logged to Supabase

---

## 📈 Metrics

**Sentence Transformer Retriever Model:**

| Metric     | Fine-Tuned `bge-base-en-v1.5` | Base `bge-base-en-v1.5` |
| ---------- | :---------------------------: | :---------------------: |
| Recall\@1  |           **0.456**           |          0.214          |
| Recall\@3  |           **0.693**           |          0.361          |
| Recall\@5  |           **0.758**           |          0.422          |
| Recall\@10 |           **0.836**           |          0.500          |
| MRR        |           **0.595**           |          0.315          |

**Model Details**: [JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)

<br />

**Alternative Light-Weight Model:**
  
| Metric      | Fine-Tuned `all-minilm-l6-v2` | Base `all-minilm-l6-v2` |
|-------------|:-----------------------------:|:-----------------------:|
| Recall@1    |           **0.428**           |          0.149          |
| Recall@3    |           **0.657**           |          0.258          |
| Recall@5    |           **0.720**           |          0.309          |
| Recall@10   |           **0.795**           |          0.382          |
| MRR         |           **0.563**           |          0.230          |

**Model Details**: [JJTsao/fine-tuned_movie_retriever-all-minilm-l6-v2](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-all-minilm-l6-v2)

<br />

**Evaluation setup**:
- Dataset: 3,598 held-out metadata and vibe-style natural queries
- Method: Top-k ranking using cosine similarity between query and positive documents
- Goal: Assess top-k retrieval quality in recommendation-like settings

---

## 🛠️ Development

### Backend
```bash
# Env
export QDRANT_ENDPOINT=...
export QDRANT_API_KEY=...
export SUPABASE_URL=...
export SUPABASE_API_KEY=...
export OPENAI_API_KEY=...

# Run
uvicorn main:app --reload --port 7860
```

### Frontend
```bash
npm install
npm run dev
# build: npm run build
```

---

## 📝 License
MIT
