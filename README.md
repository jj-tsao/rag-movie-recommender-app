# 🎬 Reelix AI – Personalized Movie & TV Discovery Agent

**Reelix** is an AI-native discovery agent that understands *vibes* and turns them into cinematic picks.

[![Netlify](https://img.shields.io/badge/Live%20Site-Netlify-42b883?logo=netlify)](https://reelixai.netlify.app/)
[![Retriever Model](https://img.shields.io/badge/Retriever%20Model-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)
[![Intent Classifier](https://img.shields.io/badge/Intent%20Classifier-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/intent-classifier-distilbert-moviebot)
[![CE Reranker](https://img.shields.io/badge/CE%20Reranker-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/movietv-reranker-cross-encoder-base-v1)
[![Made with FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://jjtsao-rag-movie-api.hf.space/docs#/)
[![Built with React](https://img.shields.io/badge/Frontend-React-61dafb?logo=react)](https://reelixai.netlify.app/)
![License](https://img.shields.io/github/license/jj-tsao/rag-movie-recommender-app)

---

👉 Try our **Live Product** here: [**Reelix AI**](https://reelixai.netlify.app/)

---

Reelix finds your next favorite watch by learning your **personal preferences**, evolving **taste**, and preferred **vibes** (themes, tone, pacing, genres).

Architecturally, Reelix is an **AI-native discovery agent** built on top of a modern **hybrid recommendation system**. A small team of collaborating agents sits above hybrid retrieval, cross-encoder reranking, and LLM-based explainability.

Under the hood, this agentic system uses:

- **Agentic workflow (3 collaborating agents)**  
  - **Orchestrator Agent** — parses user queries + recent context, infers intent, and keeps a structured plan (retrieval depth, filters, personalization inputs) and short-term session memory alive across multi-turn interactive iterations.  

  - **Retrieval & Ranking Agent** — executes that plan with a **RAG-based, hybrid retrieval pipeline**: dense + sparse (BM25) retrieval over the catalog, fusion, metadata/cross-encoder reranking, and a final LLM vibe-matching pass over a small candidate pool.  

  - **Reasoning & Explanation Agent** — takes the ranked candidates + taste profile and generates grounded “Why you might enjoy it” rationales, streaming them to the UI and writing them to Supabase + Redis as logged signals for reuse, taste profile updates, offline analysis, and model / ranking retraining.

- **Hybrid retrieval engine**  
  - **Query encoding & expansion** — take natural-language vibe queries (“neo-noir psychological thriller”, “slow-burn sci-fi drama”) and turn them into dense + sparse signals (embeddings, BM25 terms, optional expansions / boosts by LLM).  
  - **Dense** — fine-tuned SentenceTransformers (`bge-base-en-v1.5`) over titles, synopsis, and curated metadata.  
  - **Sparse** — BM25 over cleaned text for lexical precision and long-tail matches.  
  - **Fusion** — ANN over dense vectors + BM25 ranked lists, combined with RRF / weighted fusion to build a robust candidate set.

- **Multi-stage ranking (multi-objective)**  
  - A **metadata-aware scorer** combines content quality, popularity, freshness, and diversity / de-dupe objectives.  
  - A **cross-encoder reranker** re-scores a small window (e.g. top-30) for precise final ordering.  
  - **LLM-assisted vibe matching** (narrow pass) — an LLM score is blended into ranking for a small candidate pool, improving alignment to the user’s free-form vibe.

- **Personalization**  
  - A **user taste vector** built from interactions (love / like / dislike, star ratings, watchlist, trailer watch, etc.).  
  - Cold-start behavior falls back to content-centric priors (global popularity / quality) plus explicit user preference signals (genres, services, etc.).


- **Grounded LLM synthesis**  
  - The **Reasoning & Explanation Agent** generates “Why you might enjoy it” rationales grounded in the ranked candidates + taste profile.  
  - Results are streamed via SSE to the UI and cached in Supabase + Redis for reuse.


The result is a fast, AI-led natural language **“Explore by Vibe”** and **For-You feed** experience that **adapts** in real time as users interact.


---
## ✨ Core Experiences

- **Taste Onboarding (`/taste`)**  
  Quickly signal your preferences (genre / vibe picks; Love / Like / Dislike). The agents use this to initialize your **user taste vector**, which the Orchestrator Agent pulls into every subsequent plan and refines as you give more feedback.

- **Explore by Vibe (`/query`)**  
  Type “psychological thrillers with a satirical tone”. The **Orchestrator Agent** parses your natural-language vibe, builds a retrieval plan (depth, filters, personalization), and calls the **Retrieval & Ranking Agent** + **Reasoning & Explanation Agent** to stream back grounded, vibe-matched recommendations.

- **For-You Feed (`/discover`)**  
  A personalized grid of picks generated by the same multi-agent loop. The Orchestrator Agent leans more heavily on your **taste history**; each card streams a short “Why you might enjoy it” rationale from the Reasoning & Explanation Agent, powered by ranked context from the Retrieval & Ranking Agent.

- **Add to Watchlist (`/watchlist`)**  
  Save titles to watch later, flip to “Watched,” and (optionally) rate 1–10 — all in one flow. Optimistic UI + idempotent API; every interaction emits **logged signals** that update your taste vector and feed into future agent plans, offline analysis, and model / ranking improvements.

### Quick Look

> Reelix understands your vibe and curates markdown-rich suggestions, trailers, and rationale in real time.

<img width="1050" height="890" alt="Image" src="https://github.com/user-attachments/assets/f900b15b-431b-4d0c-8135-0d1bce473c00" />


---

## ✨ Core Experiences

- **Taste Onboarding (`/taste`)**  
  Quickly signal your preferences (genre / vibe picks; Love / Like / Dislike;). The agents use this to initialize your **user taste vector**, which the Orchestrator Agent pulls into every subsequent plan and refines as you give more feedback.

- **Explore by Vibe (`/query`)**  
  Type “psychological thrillers with a satirical tone”. The **Orchestrator Agent** parses your natural-language vibe, builds a retrieval plan (depth, filters, personalization), and calls the **Retrieval & Ranking Agent** + **Reasoning & Explanation Agent** to stream back grounded, vibe-matched recommendations.

- **For-You Feed (`/discover`)**  
  A personalized grid of picks generated by the same multi-agent loop. The Orchestrator Agent leans more heavily on your **taste history**; each card streams a short “Why you might enjoy it” rationale from the Reasoning & Explanation Agent, powered by ranked context from the Retrieval & Ranking Agent.

- **Add to Watchlist (`/watchlist`)**  
  Save titles to watch later, flip to “Watched,” and (optionally) rate 1–10 — all in one flow. Optimistic UI + idempotent API; every interaction emits **logged signals** that update your taste vector and feed into future agent plans, offline analysis, and model / ranking improvements.

### Quick Look

> Reelix understands your vibe and curates markdown-rich suggestions, trailers, and rationale in real time.


---

## 🧠 How It Works – Agentic Workflow at a Glance

At runtime, Reelix is a **three-agent system** sitting on top of a hybrid retrieval + ranking engine:

```text
Taste Signals ──▶ Taste Vector ─────────────┐
                                            │
User Query ───────────────┐                 │
                          ▼                 │
                 Orchestrator Agent ◀───────┘
                          │
                          ▼
               Retrieval & Ranking Agent
                          │
                          ├────────────▶ Initial JSON to UI (candidates, metadata)
                          ▼
             Reasoning & Explanation Agent
                          │
     ┌────────────────────┴────────────────────┐
     ▼                                         ▼
  SSE "why" to UI                      Logs + Cache (Supabase / Redis)
                                              │
                                              ▼
                                   Taste Updates, Analysis, Retraining
```

### 1) Orchestrator Agent

**Agentic orchestration layer** — *“What should we do next?”*

- **Understands intent from conversation**  
  Parses the current query plus recent turns to infer what the user is trying to do:
  - Explore by Vibe, refresh For-You, refine results, focus on a franchise/actor, adjust filters, etc.

- **Builds a small, explicit plan**  
  - Derives retrieval needs (dense vs. sparse depth)  
  - Assembles filters (genres, year range, streaming providers)  
  - Decides how much personalization to apply (taste vector, recent interactions)

- **Routes to other agents and tools**  
  - Calls the **Retrieval & Ranking Agent** with the constructed plan to get a high-quality candidate set  
  - Calls the **Reasoning & Explanation Agent** to generate “Why you might enjoy it” rationales for those candidates  
  - Can trigger taste profile updates or logging flows when appropriate

- **Handles multi-turn refinement**  
  - Treats follow-ups as **plan edits** rather than isolated queries  
  - Preserves `query_id` and ticket-store state so downstream tools keep operating over the same evolving candidate pool instead of starting from scratch each time


### 2) Retrieval & Ranking Agent

**Hybrid retrieval + multi-stage ranking layer** — *“What are the best candidates?”*

- **Hybrid retrieval (RAG-style)**  
  - Calls into Qdrant dense + sparse (BM25) to build a high-quality candidate set:  
    - Dense retrieval over fine-tuned `bge-base-en-v1.5` embeddings  
    - Sparse retrieval via BM25 over normalized text  
    - RRF / weighted fusion to merge dense + sparse signals

- **Metadata-aware reranking**  
  - Rating, popularity, recency/freshness  
  - Optional genre / vibe alignment  
  - Diversity / de-dupe to avoid franchise spam and near-duplicates

- **Cross-encoder + LLM vibe pass**  
  - Runs a **cross-encoder reranker** on a small window (e.g. top-30), then fuses CE scores back into the final ranking  
  - Optionally calls an LLM on a small candidate pool to score how well each title matches the user’s free-form vibe description and feeds that signal back into ranking

- **Fast path to UI**  
  - Returns a **ranked candidate set with metadata** (titles, posters, scores) immediately so the frontend can render cards and layout **before** why-copy is ready.


### 3) Reasoning & Explanation Agent

**Reasoning & explanation + streaming** — *“Why these, and what next?”*

- **Consumes**  
  - Ranked candidates from the Retrieval & Ranking Agent  
  - The user’s taste profile and recent interactions  
  - The current mode (Explore by Vibe vs. For-You)

- **Builds structured prompts to**  
  - Generate “**Why you might enjoy it**” copy per title  
  - Avoid self-references or hallucinations  
  - Produce markdown-friendly output for movie/TV cards

- **Runs in parallel with UI rendering**  
  - Kicks off as soon as candidates are available, while the UI is already showing cards and skeletons.

- **Streams results via SSE / JSONL**  
  - `started` → incremental `why_delta` events per `media_id` → `done`  
  - Inserts the final “why” copy and associated metadata to Supabase and Redis for reuse


### 4) Signals, feedback loops & taste updates

- Logs final recs and user feedback (interactions, ratings, watchlist actions) into Supabase + Redis.  
- Aggregates these signals into an updated **taste vector**, which the Orchestrator Agent pulls into future plans.  
- Exposes rich logged signals (scores, why-copy, interaction outcomes) for **offline analysis** and future **model / ranking retraining**.

Over time, these feedback loops turn Reelix into a richer **discovery agent**, not just a static recommender: it can adapt its plans, retrieval parameters, and even suggestion style based on how you interact.

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

### 4) Watchlist (`/watchlist`)
Lets users save titles to watch later, mark them as watched, and optionally rate them (1–10). Designed to be idempotent and fast, with optimistic UI updates. Stores rows in Supabase (unique on `user_id` + `media_id`) and emits lightweight signals that feed back into the taste profile.

1) `POST /watchlist`
   - Adds or upserts an item in the user’s watchlist (reactivates if previously soft-deleted).
   - Input fields like `title`, `poster_url`, etc. are denormalized hints to render immediately; canonical metadata lives in Qdrant/TMDB.
   - Emits an interaction event (`watchlist_add`) for taste-signal logging.
  
2) `GET /watchlist`
   - Lists the user’s watchlist items, with optional filters/pagination.
   - Hydrates metadata fields like genres, release_year, artworks, and why_summary, so the client avoids a second fetch.

3) `PATCH /watchlist/{media_id}`
   - Atomically updates status and/or rating (ideal for “✓ Watched ▾ → quick-rate”).
   - Emits an interaction event (`rating`) when a rating is present for taste-signal logging.

4) `DELETE /watchlist/{media_id}`
   - Remove from watchlist.
   - Soft delete the item. Sets `deleted_at`, `deleted_reason`, and derives `is_active=False`.


### **Frontend details**
- `/discover` loads a grid of picks, then begins SSE streaming of “why” and ratings, updating each card live.
- Users can **Love / Like / Not for me** or **watch trailer**; feedback is logged and triggers controlled taste rebuilds.
- **Smart rebuild controller**: after any rating, start/refresh a 10s timer; if ≥2 ratings when the timer fires, rebuild—**max 1 rebuild per 2 minutes**; queue one pending rebuild during cooldown.

---
## 🏗️ Recommendation Pipeline Architecture (High‑Level)

```
User Interactions ──▶ Taste Vector (user tower)
                                    │
                                    │
User Prompt ──▶ Query Encoder ──────┤
                                    │ 
                                  Filters (genres, year, streaming provider)
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

- **Dense**: fine‑tuned `bge-base-en-v1.5` embeddings
- **Sparse**: BM25 with tokenization/stop‑word cleanup
- **Reranking**: weighted blend of semantic + sparse + quality + popularity (+ optional genre overlap)
- **CE**: `BERT` Cross‑Encoder pairwise reranker
- **Streaming**: reasons & markdown are delivered as **newline-delimited JSON over SSE**.
- **Bootstrap & lifespan** — on startup, the backend loads the embedder, BM25 index, CE reranker, Qdrant client, config, and ticket store.
- **Pipeline / recipe runner** — the FastAPI layer maps each request to a small set of pipeline “recipes” (`interactive`, `for_you_feed`, etc.) that define inputs (query vs. taste), retrieval params, and LLM prompt envelopes, and then invokes the three-agent workflow with the defaults.


**Tunable knobs** (with sensible defaults):

- Retrieval depths: `dense_depth=300`, `sparse_depth=100`
- Fusion: `rrf_k=60`
- Metadata weights: `{dense=0.56, sparse=0.14, rating=0.14, popularity=0.04, genre=0.12,}`
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
