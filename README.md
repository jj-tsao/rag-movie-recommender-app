# Reelix AI – Personalized Movie Discovery Agent

[![Netlify](https://img.shields.io/badge/Live%20Site-Netlify-42b883?logo=netlify)](https://reelixai.netlify.app/)
[![Retriever Model](https://img.shields.io/badge/Retriever%20Model-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)
[![Intent Classifier](https://img.shields.io/badge/Intent%20Classifier-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/intent-classifier-distilbert-moviebot)
[![CE Reranker](https://img.shields.io/badge/CE%20Reranker-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/movietv-reranker-cross-encoder-base-v1)
[![Made with FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://jjtsao-rag-movie-api.hf.space/docs#/)
[![Built with React](https://img.shields.io/badge/Frontend-React-61dafb?logo=react)](https://reelixai.netlify.app/)
![License](https://img.shields.io/github/license/jj-tsao/reeli)

---

👉 Try the **Live Product** here: [**Reelix AI**](https://reelixai.netlify.app/)

---

**Reelix** is an AI-native movie discovery agent that understands your preferred vibe, learns your taste, and recommend films you'll actually love.

Under the hood, Reelix is a multi-agent system with four collaborating AI agents spanning intent understanding & planning, candidate curation, next-step guidance, and fit explanations:

1. **Orchestrator Agent**: parses queries, builds a structured retrieval plan, and manages multi-turn session memory
2. **Curator Agent**: scores candidates on genre, tone, theme, and structural fit via parallel LLM evaluation
3. **Reflection Agent**: proposes a concrete next-step direction after each recommendation turn
4. **Explanation Agent**: streams personalized “why you’ll enjoy it” rationales to the UI

The agents are backed by a hybrid recommendation pipeline (dense + sparse retrieval, multi-step reranking) and a user taste vector that evolves with every rating, reaction, and refinement.

---
## Core Experiences

- **Explore by Vibe (`/explore`)**
  Type a vibe — “psychological thrillers with a satirical tone on Netflix” — and get a curated slate with streaming rationales explaining why each pick fits, plus a next-step suggestion to keep exploring.

- **Taste Onboarding (`/taste`)**
  Pick genres and vibes, react to titles (Love / Like / Not for me), and the system builds a taste profile that sharpens every recommendation going forward.

- **For-You Feed (`/discover`)**
  A personalized grid of picks that leans on your taste history. Each card streams a short “Why you might enjoy it” write-up as it loads.

- **Watchlist (`/watchlist`)**
  Save titles, mark as watched, rate 1–10 — every interaction feeds back into your taste profile and future recommendations.

### Quick Look

> Reelix understands your vibe and curates markdown-rich suggestions, trailers, and rationale in real time.

<img width="1061" height="1065" alt="Image" src="https://github.com/user-attachments/assets/99219ff0-2fa9-4c08-843b-3a49efbeaa71" />

---

## Architecture - Agentic Workflow and Recommendation Pipeline

At runtime, Reelix is a **four-agent system** (Orchestrator → Curator → Reflection → Explanation) with a sophisticated recommendation engine:

```text
  Taste Signals ─▶ Taste Vector ───┐
                                   │
  User Query + context ────────┐   │
                               ▼   ▼
                        Orchestrator Agent (parse → RecQuerySpec; generate opening summary)
                                 │
                                 ├─ SSE: started ──────────────────────▶ UI
                                 ├─ SSE: opening (summary, spec) ──────▶ UI
                                 │
                                 ▼
                       Recommendation Pipeline Tool (retrieve → fuse → rerank)
                                 │
                                 ▼
                          Curator Agent (parallel LLM scoring → tier → select)
                                 │
                                 ├─ Persist session memory on Redis
                                 ├─ SSE: recs (slate + metadata) ──────▶ UI
                                 │
                                 ▼
                         Reflection Agent (analyze slate → propose next step)
                                 │  (soft weighted next step strategy selection)
                                 │
                                 ├─ SSE: next_steps ───────────────────▶ UI
                                 ├─ Persist suggestion + strategy → session memory (Redis)
                                 │
                                 ▼
                         Explanation Agent ("why" write-up → stream JSONL)
                                 │
                                 ├─ SSE: why events ────────────────────▶ UI
                                 ├─ SSE: done ──────────────────────────▶ UI
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
       Cache "why" (Redis)           Logs (Supabase: agent decisions, user interactions)
                                                      ▼
                                     Taste Updates, Analysis, Retraining
```


### 1) Orchestrator Agent

**Agentic orchestration layer** — *"What should we do next?"*

The orchestrator converts messy natural language into a clean `RecQuerySpec` and keeps it stable across multi-turn refinement.

- **Understands intent from conversation**
  - Interprets the current message in the context of recent turns
  - Decides whether this is a new request, refinement, or a meta/non-rec question

- **Generates fast opening summary**
  - Produces a 2-sentence opening summary (before curator runs) for immediate UI feedback via SSE
  - Summary is based on RecQuerySpec and provides context while recommendations load

- **Builds a small, explicit plan** (`RecQuerySpec` as a "living object")
  - Parse intents into precise query_text, genres, sub-genres, tone, narrative shape
  - Assembles filters (genres, year range, streaming providers, etc.)
  - Decides how much personalization to apply (taste vector, recent interactions)

- **Routes to specialist agents and tools**
  - Calls the **recommendation_tool** (pipeline) with the constructed plan to get candidates
  - The pipeline calls the **Curator Agent** for evaluation and selection
  - Calls the **Explanation Agent** to generate "Why you might enjoy it" rationales for the recommended titles
  - Trigger taste profile updates or logging flows when appropriate

- **Handles multi-turn refinement**
  - Treats follow-ups as **plan edits** rather than isolated queries
  - Preserves `query_id` and session state so downstream tools keep operating over the same evolving context instead of starting from scratch each time


### 2) Recommendation Pipeline (Tool)

**Hybrid retrieval + multi-stage ranking layer** — *"What are the best candidates?"*

This deterministic pipeline executes the `RecQuerySpec` from the orchestrator, retrieves and ranks candidates, then calls the curator agent for final evaluation.

- **Hybrid retrieval (RAG-style)**
  - Calls into Qdrant dense + sparse (BM25) retrieval to build a high-quality candidate set:
    - Dense retrieval over fine-tuned `bge-base-en-v1.5` embeddings
    - Sparse retrieval via BM25 over normalized text
    - RRF / weighted fusion to merge dense + sparse signals

- **Metadata-aware + cross-encoder reranking**
  - Rating, popularity, recency/freshness, genre alignment
  - Diversity / de-dupe to avoid franchise spam and near-duplicates
  - Runs an optional **cross-encoder reranker** on a small window (e.g. top-30), then fuses CE scores back into the final ranking

- **Calls Curator Agent for evaluation**
  - Passes candidates and RecQuerySpec to the curator agent
  - Curator evaluates each candidate on fit dimensions
  - Returns tiered and selected recommendations


### 3) Curator Agent

**LLM-based candidate evaluation layer** — *"How well do these match the vibe?"*

This agent evaluates candidates from the recommendation pipeline using LLM reasoning to score fit across multiple dimensions.

- **Parallel evaluation for reduced latency**
  - Splits candidates into multiple batches
  - Runs parallel LLM calls via `asyncio.gather` to reduce latency
  - Merges results for final selection

- **Multi-dimensional scoring**
  - Evaluates each candidate on 4 dimensions (0-2 scale):
    - `genre_fit`: How well genres/sub-genres match the request
    - `tone_fit`: How well emotional vibe/tone matches
    - `theme_fit`: How well thematic ideas align
    - `structure_fit`: How well narrative structure matches
  - Uses RecQuerySpec and candidate metadata for structured evaluation

- **Tiering and selection**
  - Categorizes candidates as: strong_match, moderate_match, or no_match
  - Applies tier-based selection logic to produce final recommendations
  - Returns curated slate to orchestrator for SSE streaming to UI

- **Fast path to UI**
  - Returns a **ranked slate with metadata** (titles, posters, scores) via SSE immediately so the frontend can render cards and layout **before** why-copy is ready.


### 4) Reflection Agent

**Next-step guidance** — *”Where should we explore next?”*

After each recommendation turn, the Reflection Agent analyzes the curated slate and proposes a concrete next direction to guide continued discovery. It runs before the Explanation Agent for lower latency — the next-step suggestion is fast (single short LLM call) and streams to the UI while the heavier explanation generation follows.

- **Runs post-curator**
  - Executes only in RECS mode, after curator evaluations
  - Streams an SSE `next_steps` event with strategy and suggestion text
  - 10-second timeout with graceful degradation — never blocks the main response

- **Four strategies** (LLM chooses per turn with soft weighting)
  - `deep_dive`: Zooms into one title's specific quality — its sub-genre, directorial style, or narrative approach
  - `follow_the_thread`: Names a pattern across the results and proposes where it leads — a different corner of cinema that shares the same thread
  - `reframe`: Keeps the core appeal but repackages it in a completely different context — swaps the tone, decade, or setting
  - `wildcard`: Identifies a deeper emotional or structural quality driving the results and connects it to a film from a completely different genre

- **Soft weighting for strategy diversity**
  - Recent strategy history persisted as `recent_reflection_strategies` list in session state (Redis)
  - Soft nudge toward underused strategies based on a rolling window of the last 3 turns
  - Few-shot examples dynamically selected from preferred strategies to prime the LLM
  - Hard block on the immediate last strategy to prevent repetition

- **Session memory integration for multi-turn flow**
  - Persists suggestion as `last_admin_message` in session state (Redis)
  - On the next turn, the orchestrator recognizes short affirmations (“yes”, “sure”, “let's go”) and auto-advances the suggestion into a new recommendation query
  - Enables fluid, conversational discovery without requiring users to rephrase

- **Full instrumentation**
  - All attempts (success/timeout/error) logged to `reflection_logs` table with strategy, suggestion, latency, token counts, and tier stats
  - Key files: `reflection_agent.py`, `reflection_prompts.py`


### 5) Explanation Agent

**Reasoning & explanation** — *”Why these, and what next?”*

- **Consumes**
  - Ranked slate from the **Recommendation Pipeline** and **Curator Agent**
  - The user's taste profile and recent interactions
  - The current mode (Explore by Vibe vs. For-You)

- **Builds structured prompts to**
  - Generate “**Why you might enjoy it**” copy per title
  - Avoid self-references or hallucinations
  - Produce markdown-friendly output for movie cards

- **Runs in parallel with UI rendering**
  - Kicks off as soon as the slate is available, while the UI is already showing cards and skeletons.

- **Streams results via SSE / JSONL**
  - Incremental `why_delta` events per `media_id` → `done`
  - Inserts the final “why” copy and associated metadata to Redis Supabase for cache and analysis


### 6) Signals, feedback loops & taste updates

The system maintains comprehensive logging across two layers for analysis, debugging, and continuous improvement:

#### Layer 1: Recommendation Pipeline Logging (All Endpoints)
- **`rec_queries`** - Query metadata (query_id, filters, user context, timestamp)
- **`rec_results`** - Per-candidate pipeline scores (dense_score, sparse_score, metadata_score, final_score, rank)

#### Layer 2: Agent Decision Logging (Agent Endpoints Only)
- **`agent_decisions`** - Orchestrator decisions (mode routing, RecQuerySpec generation, LLM usage, latency)
- **`curator_evaluations`** - Per-candidate fit scores (genre_fit, tone_fit, theme_fit, structure_fit, tier, is_served, final_rank)
- **`tier_summaries`** - Aggregate statistics (strong/moderate/no_match counts, selection_rule applied, curator latency)
- **`reflection_logs`** - Reflection agent attempts (strategy, suggestion, status, latency, token counts, tier context)

#### Feedback Loop Integration
- **User interactions** (Love/Like/Dislike, ratings, watchlist actions, trailer views) logged to Supabase
- **Taste vector updates** - Aggregates signals and rebuilds user taste profile
- **Session memory** - Persists query context, RecQuerySpec, and final_recs to Redis for multi-turn conversations
- **"Why" explanations** - Cached in Supabase + Redis for reuse and analysis

#### Layer 3: Evaluation Jobs (Data Pipeline)

Automated evaluation that runs on logged data to measure recommendation and explanation quality over time.

**Daily Metrics** (`python -m jobs.eval_metrics`)
- Computes 20+ metrics across 6 groups from logging tables and upserts to `daily_metrics`:
  - **Cost**: request count, total input/output tokens, avg tokens per query
  - **Latency**: end-to-end p50/p95, per-stage p50 (orchestrator, pipeline, curator, reflection)
  - **Curator quality**: tier distribution (strong/moderate/no_match rates), served ratio, avg fit score, fit-vs-pipeline-score correlation
  - **Errors**: error rate, error count by stage
  - **Routing**: CHAT vs RECS mode distribution
  - **Judge**: aggregated judge scores (if `eval_judge` has run), judge-curator correlation
- Supports backfills: `--days 7` computes the last 7 days

**LLM-as-Judge** (`python -m jobs.eval_judge`)
- Samples completed agent queries from a target date and runs two independent LLM judge calls per query:
  1. **Recommendation quality** (relevance + novelty, 1–5) — evaluates curator picks *without* seeing "why" explanations to avoid bias
  2. **Explanation quality** (1–5) — evaluates explanation agent output *with* "why" text
- This separation cleanly isolates curator vs explanation agent quality: if relevance drops, it's the curator; if explanation quality drops, it's the explanation agent
- Scores persisted to `judge_evaluations` with eval_run_id, curator tier/fit for correlation analysis
- Configurable: `--sample-size 100 --model gpt-4o-mini`

#### Analysis & Retraining
- Join `curator_evaluations` with `rec_results` on (query_id, media_id) to analyze fit scores vs. pipeline scores
- Track orchestrator planning accuracy and curator tier distribution
- Exposes rich signals for **offline analysis** and future **model/ranking retraining**

Over time, these feedback loops turn Reelix into a richer **discovery agent**, not just a static recommender: it can adapt its plans, retrieval parameters, and even suggestion style based on how you interact.

---

## Key API Endpoints

### Discovery Endpoints

#### 1) Agentic Discovery by Vibe (`/explore`)
Agent-powered conversational search with streaming SSE responses.

1) `POST /discovery/explore`
   - Orchestrator Agent parses natural language query and builds RecQuerySpec
   - Streams SSE events: `started` → `opening` → `recs` → `next_steps` → `done`
   - Opening summary is generated upfront for fast UI paint
   - Executes recommendation pipeline → curator agent in background
   - Returns final recommendations with why URL for explanations
   - Reflection Agent proposes a next-step suggestion for multi-turn discovery
   - Logs orchestrator decisions, curator evaluations, tier summaries, and reflection attempts

2) `GET /discovery/explore/why?query_id=...` (SSE)
   - Explanation Agent generates personalized "why" rationales
   - Streams JSONL events with `{media_id, why}` for each recommendation
   - Caches results in Supabase + Redis for reuse

3) `POST /discovery/explore/rerun`
   - Chip rerun endpoint: patches provider/year filters and reruns the same pipeline path
   - Bypasses orchestrator LLM, using last_spec from session state
   - Returns updated recommendations with new filters applied

#### 2) For-You Feed (`/for-you`)
Personalized feed based on user taste profile. 

1) `POST /discovery/for-you`
   - Queries the user's taste profile from the database
   - Runs the **for_you_feed** recipe (dense + BM25 + metadata + CE reranker) against the **user taste context** to fetch **Top-K** candidates
   - Builds the LLM prompt with those candidates and **persists it in the ticket store** (keyed by `query_id`)
   - Returns the candidate list with metadata (year, genres, posters, trailers, etc.) **plus** a `stream_url` for explanations
   - Logs a **query-intake record** and a **Top-K candidate snapshot** (IDs, ranks, and **per-signal score traces**)

2) `GET /discovery/for-you/why?query_id=...` (SSE)
   - Reads the LLM prompt and Top-K candidates from the ticket store
   - Performs LLM reasoning to generate concise "why you might enjoy it" copy
   - Streams events `{started, why_delta, done}` where `why_delta` includes `media_id`, optional `imdb_rating` and `rotten_tomatoes_rating`, and `why_you_might_enjoy_it` (markdown)

### User Profile & Preferences

#### 3) Taste Profile (`/taste_profile`)
Build and maintain a personalized **taste vector** from user interactions and preferences. Stores profile state in Supabase and powers the For-You feed and agent-based ranking.

1) `POST /taste_profile/rebuild`
   - Aggregates **user signals**: recent interactions (e.g., Love / Like / Not for me, trailer views), selected genres/vibes, and any provider filters
   - Fetches the corresponding **item embeddings** from Qdrant and computes a **taste vector** (weighted aggregation + normalization)
   - **Upserts** the profile into Supabase, recording metadata such as `vector_dim`, `n_signals_used`, `build_version`, and timestamps

2) `GET /taste_profile/me`
   - Returns the latest **profile metadata** and a safe subset of fields for inspection
   - Useful for gating UX ("has profile been built?") and for debugging profile freshness across sessions

#### 4) User Settings (`/users/me/settings`)
Manage user preferences for genres, keywords, and other personalization settings.

1) `PATCH /v2/users/me/settings/preferences`
   - Upsert user preferences (genres_include, keywords_include)
   - Updates stored in Supabase `user_preferences` table
   - Used during taste profile rebuilds and recommendation filtering

### User Data Management

#### 5) Watchlist (`/watchlist`)
Lets users save titles to watch later, mark them as watched, and optionally rate them (1–10). Designed to be idempotent and fast, with optimistic UI updates.

1) `POST /watchlist`
   - Adds or upserts an item in the user's watchlist (reactivates if previously soft-deleted)
   - Input fields like `title`, `poster_url`, etc. are denormalized hints to render immediately; canonical metadata lives in Qdrant/TMDB
   - Emits an interaction event (`watchlist_add`) for taste-signal logging

2) `GET /watchlist`
   - Lists the user's watchlist items, with optional filters/pagination
   - Hydrates metadata fields like genres, release_year, artworks, and why_summary, so the client avoids a second fetch

3) `PATCH /watchlist/{media_id}`
   - Atomically updates status and/or rating (ideal for "✓ Watched ▾ → quick-rate")
   - Emits an interaction event (`rating`) when a rating is present for taste-signal logging

4) `DELETE /watchlist/{media_id}`
   - Remove from watchlist
   - Soft delete the item. Sets `deleted_at`, `deleted_reason`, and derives `is_active=False`

#### 6) Interactions (`/interactions`)
Track user interactions with recommendations (Love, Like, Not for me, trailer views, etc.) for taste profile updates and analytics.

1) `POST /interactions`
   - Log user interaction events (e.g., `love`, `like`, `not_for_me`, `trailer_view`)
   - Stores interaction in Supabase with timestamp and metadata
   - Feeds into taste profile rebuilds and recommendation retraining
   - Used by smart rebuild controller to trigger controlled taste updates (max 1 rebuild per 2 minutes)

### Telemetry & Logging

#### 7) Telemetry (`/discovery/telemetry`)
Analytics and logging endpoints for tracking recommendation performance and caching explanations.

1) `POST /discovery/telemetry/final_recs`
   - Log final recommendations shown to user (fire-and-forget)
   - Caches LLM-generated "why" explanations in Redis for reuse
   - Skips caching for items where `why_source == "cache"` to avoid redundant writes
   - Writes to Supabase for offline analysis and A/B testing

---
## Recommendation Pipeline Architecture (High‑Level)

```
User Interactions ──▶ Taste Vector (Long term memory)
                                    │
                                    ▼
              User Prompt ──▶ Orchestrator Agent (LLM)
                                    │
                                    ▼
                               RecQuerySpec 
                                    │
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
           Sparse Search                         Dense Search
              (BM25)                   (fine-tuned sentence transformer)
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    │
                                    ▼
                 RRF #1: Candidate Pool (dense ⊕ sparse)
                                    │
                                    ▼
                        Metadata Rerank (top 100)
                (genre, rating, popularity, freshness)
                                    │
                                    ▼
                            Top-K Candidates
                                    │
                                    ▼
                          Curator Agent (LLM)
                          (parallel batches)
                                    │
                       Evaluate fit on 4 dimensions:
                         • genre_fit (0-2)
                         • tone_fit (0-2)
                         • theme_fit (0-2)
                         • structure_fit (0-2)
                                    │
                                    ▼
                     Tier Assignment (based on scoring)
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
      strong_match            moderate_match            no_match
           │                        │                        │
           └────────────────────────┴────────────────────────┘
                                    │
                                    ▼
                          Final Selection Logic
                          (dynamic, tier-based)
                                    │
                                    ▼
                            Top N Final Recs (~8)
                                    │
                                    ▼
                            UI (streaming SSE)
                                    │
                                    ▼
                          Reflection Agent (LLM)
                      (propose next-step suggestion)
                                    │
                                    ▼
                        UI (next_steps SSE event)
                        + Session Memory (Redis)
                                    │
                                    ▼
                         Explanation Agent (LLM)
                     (generate "why" for each item)
                                    │
                                    ▼
                             UI (streaming SSE)

```

**Tunable knobs** (with sensible defaults):

- Retrieval depths: `dense_depth`, `sparse_depth`
- Fusion: `rrf_k`
- Metadata weights: `{dense, sparse, rating, popularity, recency, genre}`
- Curator pass size: `top-k`
- Curator dimensions: `genre_fit`, `tone_fit`, `theme_fit`, `structure_fit`
- Tiering criteria: dynamic `final_recs` count from each tier

---
## Tech Stack

| Layer        | Tech                     |
|-------------|--------------------------|
| Frontend               | React + Vite + Tailwind CSS             |
| Backend                | FastAPI (Python) + Docker                            |
| Embedding/ Retrieval   | SentenceTransformers (fine-tuned `bge-base-en-v1.5`) + BM25 |
| Reranking              | **Cross‑Encoder (fine-tuned `bert-base-uncased`)** + Metadata + **RRF** |
| Intent Classification  | DistilBERT (fine-tuned `distilbert-base-uncased`)    |
| Tokenization           | NLTK (Natural Language Toolkit)                      |
| Vector DB              | Qdrant (hybrid search)                               |
| Storage                | Supabase (user profiles, interactions, logs)              |
| Ticket Store           | Redis-based temporary storage (LLM prompts/candidates) |
| State Store            | Redis-based session memory (multi-turn agent conversations) |
| Why Cache | Redis-based why rationale caching (for-you feed reuse) |
| Chat Completion        | OpenAI API (streamed JSONL/SSE)                      |
| Movie Metadata         | TMDB (The Movie Database) API                        |
| Model Hosting          | Hugging Face Hub                                     |
| Deployment             | Frontend: Netlify, Backend: Hugging Face Spaces      |

---

## Sample Query Flow

1. User enters a vibe-based prompt (e.g., _"Mind-bending sci-fi with existential themes on Netflix from the past 5 years"_)
2. Orchestrator Agent determines mode (CHAT vs RECS) and generates opening summary
3. Opening summary streams to UI immediately for fast feedback
4. RecQuerySpec is constructed with filters, genres, tone, themes
5. Recommendation Pipeline executes hybrid retrieval (dense + sparse + BM25)
6. Multi-stage ranking: metadata scorer + cross-encoder reranking
7. Curator Agent evaluates candidates in 2 parallel batches on genre/tone/theme/structure fit
8. Tier-based selection produces final recommendations
9. Reflection Agent analyzes the slate and streams a next-step suggestion (e.g., "Want to explore 70s paranoid sci-fi with that same vibe?")
10. Suggestion and strategy persisted to session memory — user can say "yes" to auto-advance into a new search
11. Explanation Agent streams personalized "why" rationales via SSE
12. UI displays cards with posters, ratings, metadata, rationale, and trailer links
13. All decisions logged to Supabase (orchestrator, curator, pipeline, explanations, reflection)

---

## Metrics

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

## Repository Structure

This is a **pnpm monorepo** using **Turborepo**:
- **apps/api** - FastAPI backend (Python 3.11+, managed with `uv`)
- **apps/web** - React frontend (Vite + TypeScript + Tailwind)
- **apps/data-pipeline** - ETL, embedding, rating enrichment, and evaluation jobs (Python 3.11+, managed with `uv`)
- **packages/python** - Shared Python packages (reelix_agent, reelix_core, reelix_ranking, reelix_retrieval, etc.)

---
## 🛠️ Development

### Monorepo (root)
```bash
pnpm install              # Install all dependencies
pnpm dev                  # Run all services via Turborepo
pnpm build                # Build all packages
```

### Backend (apps/api)
```bash
cd apps/api
uv sync                   # Install Python dependencies
source .venv/bin/activate # Activate venv

# Environment variables (create .env file)
export QDRANT_ENDPOINT=...
export QDRANT_API_KEY=...
export SUPABASE_URL=...
export SUPABASE_API_KEY=...
export OPENAI_API_KEY=...
export REDIS_URL=...

# Run API server
uvicorn app.main:app --reload --port 7860
```

### Frontend (apps/web)
```bash
cd apps/web
pnpm dev                  # Start Vite dev server (localhost:5173)
pnpm build                # Build for production
pnpm typecheck            # Type check
```

---

## License
MIT
