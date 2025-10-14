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

The result is a fast, **personal For-You recommendation feed** and a flexible **“Explore by vibe”** experience that adapts as you give feedback.

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
User Query ──▶ Dense + BM25 ──▶ Candidate Pool (RRF#1) ──▶ Metadata Rerank ──▶ CE Rerank ──▶ Final Fusion (RRF#2) ──▶ LLM "Why"
                                   ▲                                                             │
                                   │                                                             ▼
                               Filters (Streaming services/genres/year)                       SSE stream to UI
```

- **Dense**: fine‑tuned `bge-base-en-v1.5` embeddings
- **Sparse**: BM25 with tokenization/stop‑word cleanup
- **Reranking**: weighted blend of semantic + sparse + quality + popularity (+ optional genre overlap)
- **CE**: `BERT` Cross‑Encoder pairwise reranker
- **Streaming**: reasons & markdown delivered as newline-delimited JSON over SSE
- **Bootstrap & Lifespan**: loads intent classifier, embedder, BM25, CE reranker, Qdrant client, and configures ticket store.
- **Orchestrator**: Recipes (`interactive`, `for_you_feed`) define inputs (query vs taste), retrieval params, and LLM prompt envelopes.

---

## 🌐 Key API Endpoints

### 1) Taste Onboarding (`/taste`)
Create a personal taste vector from your likes/dislikes and genre/vibe signals. The service builds and stores a dense taste profile, with endpoints to **inspect** and **rebuild** your profile:
1) `POST /taste_profile/rebuild`
   Rebuilds from interactions and persists to Supabase
3) `GET /taste_profile/me`
   Returns last build metadata & vector dim

Under the hood, the rebuild process fetches user signals, loads item embeddings from Qdrant, and calls `build_taste_vector(...)`, then upserts the profile.

### 2) For-You Feed (`/discover`)
Your **For-You** page streams personalized reasons (and markdown rich movie/tv profile) per item in real-time. The flow is a two-step ticketed orchestration:

1) `POST /discovery/for-you`  
   Returns the candidate list plus a `stream_url` for reasons.

2) `GET /discovery/for-you/why?query_id=...` (SSE)  
   Streams events `{started, why_delta, done}` where `why_delta` includes `media_id`, optional `imdb_rating` and `rotten_tomatoes_rating`, and `why_you_might_enjoy_it` markdown.

The endpoint uses a **ticket store** (memory or Redis) with idle and absolute TTLs to hold LLM prompts and guard access by user id.

### 3) Vibe Query (`/query`)
Explore by vibe with free-form natural language and optional filters (providers, genres, release years, media type).

1) `POST /recommendations/interactive`
- Runs the interactive recipe (dense + BM25 + metadata + CE reranker) to fetch ~20 top candidates.  
- Builds the LLM prompt with those candidates and (if signed in) your taste context.  
- **Streams** the final recommendations **and** their “why” write-ups directly as the response body (text stream).

This flow uses the same ticket store (memory or Redis) with idle and absolute TTLs to hold LLM prompts and guard access by user id.


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
6. Retrieved medias are re-ranked based on semantic, keywords, rating, and popularity
7. Top-20 reranked results are sent to LLM for final recommendation and summary
8. UI streams response card-by-card with poster, rating, metadata, rationale, and trailer link
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
