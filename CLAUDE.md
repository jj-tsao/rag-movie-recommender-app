# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reelix is an AI-native movie discovery agent that uses a **multi-agent RAG system** for personalized recommendations. Three specialized agents collaborate:
- **Orchestrator**: Routes queries, plans structured retrieval specs, and manages session memory
- **Recommendation**: Run recommendation pipeline, and evaluates candidates on genre/tone/theme fit
- **Explanation**: Generates personalized "why you'll like it" rationales

The system combines dense embeddings (fine-tuned bge-base-en-v1.5), BM25 sparse search, cross-encoder reranking, and streaming LLM explanations.

## Repository Structure

This is a pnpm monorepo using Turborepo:
- **apps/api** - FastAPI backend (Python 3.11+, managed with `uv`)
- **apps/web** - React frontend (Vite + TypeScript + Tailwind)
- **apps/data-pipeline** - ETL + embedding + Qdrant indexing pipeline (Python 3.11+, managed with `uv`)
- **packages/python** - Shared Python packages (reelix_agent, reelix_core, reelix_ranking, reelix_retrieval, etc.)
- **packages/js/ts-sdk** - TypeScript SDK generated from OpenAPI spec via Orval
- **packages/py-sdk** - Python SDK for API client

## Development Commands

### Monorepo (root)
```bash
pnpm install              # Install all dependencies
pnpm dev                  # Run all services via Turborepo
pnpm build                # Build all packages
pnpm lint                 # Lint all packages
pnpm typecheck            # Type check all packages
pnpm generate             # Regenerate TypeScript SDK from OpenAPI spec
```

### Frontend (apps/web)
```bash
cd apps/web
pnpm dev                  # Start Vite dev server (localhost:5173)
pnpm build                # Build for production
pnpm lint                 # ESLint
pnpm typecheck            # TypeScript check
pnpm gen:db-types         # Regenerate Supabase types
```

### Backend (apps/api)
```bash
cd apps/api
uv sync                   # Install Python dependencies
source .venv/bin/activate # Activate venv

# Run API server
uvicorn app.main:app --reload --port 7860

# Run tests
pytest                           # Run all tests
pytest tests/test_first_recommendation.py  # Run specific test file
pytest -k "test_name"            # Run tests matching pattern

# Skip model loading for faster startup during development
REELIX_SKIP_RECOMMENDER_INIT=1 uvicorn app.main:app --reload --port 7860
```

### Data Pipeline (apps/data-pipeline)
```bash
cd apps/data-pipeline
uv sync                   # Install Python dependencies
source .venv/bin/activate # Activate venv

# Full indexing pipeline (fetch TMDB data → embed → upsert to Qdrant)
python -m jobs.indexing --media-type movie --media-count 10  # 10k movies
python -m jobs.indexing --media-type tv --media-count 5      # 5k TV shows

# Rating enrichment (IMDb + OMDb → Qdrant payload sync)
python -m jobs.enrich_ratings --mode daily --budget 500
python -m jobs.enrich_ratings --mode weekly --budget 1000
```

### Linting and Formatting (Python)
```bash
ruff check .              # Lint
ruff format .             # Format
black .                   # Alternative formatter
```

## Architecture

### Multi-Agent System (3 Collaborating Agents)

The system uses a sophisticated **multi-agent architecture** where specialized agents collaborate to deliver personalized recommendations:

#### 1. Orchestrator Agent (`reelix_agent/orchestrator/`)
- **Role**: Route and plan user interactions
- **Modes**: CHAT (conversational) vs RECS (recommendations)
- **Flow**:
  1. Receives user query → determines mode (CHAT vs RECS)
  2. In RECS mode: produces structured `RecQuerySpec` + **opening_summary** (2 sentences, fast)
  3. Calls `recommendation_agent` tool to execute retrieval/ranking
  4. Manages session memory and conversation state across turns
- **Key files**: `orchestrator_agent.py`, `agent_state.py`, `orchestrator_prompts.py`
- **Opening summary**: The orchestrator generates this upfront (before curator runs) for fast UI paint

#### 2. Curator Agent (`reelix_agent/curator/`)
- **Role**: Evaluate and tier candidates
- **Input**: Raw candidates from recommendation pipeline + query spec
- **Scoring**: Evaluates each candidate on three dimensions (0-2 scale):
  - `genre_fit`: How well the genres/sub-genres match the request
  - `tone_fit`: How well the emotional vibe/tone matches
  - `theme_fit`: How well the thematic ideas align
- **Parallel Evaluation**: Splits candidates into 2 batches (~6 each) and runs 2 parallel LLM calls via `asyncio.gather` to reduce latency
- **Output**:
  - Tiered evaluations (strong_match, moderate_match, no_match)
  - Final curated list using tier-based selection logic
- **Key files**: `curator_agent.py`, `curator_tiers.py`, `curator_prompts.py`

#### 3. Explanation Agent (`reelix_agent/explanation/`)
- **Role**: Generate personalized "why" explanations
- **Input**: Final recommendations + user context
- **Output**: Streaming JSONL with `{media_id, why}` for each item
- **Key files**: `explanation_agent.py`, `explanation_prompts.py`

### Agent Execution Flow
```
User Query
  → Orchestrator (plan: mode, spec, opening_summary)
    → Recommendation Tool
      → Retrieval Pipeline (dense + sparse + ranking)
      → Curator Agent (tier & evaluate candidates)
    → Return: final_recs + opening_summary
  → SSE Stream: Explanation Agent (generate "why" for each item)
```

### Recommendation Pipeline (Under the Hood)
1. **Query Encoding** - `reelix_retrieval/query_encoder.py`: Dense (fine-tuned bge-base-en-v1.5) + sparse (BM25)
2. **Retrieval** - `reelix_retrieval/base_retriever.py`: Hybrid search via Qdrant (dense + sparse vectors)
3. **Ranking** - `reelix_ranking/`: Multi-stage reranking (metadata scorer + cross-encoder)
4. **Recommendation** - `reelix_recommendation/recommend.py`: Orchestrates retrieval + ranking + RRF fusion

### Data Pipeline (apps/data-pipeline)

ETL pipeline that populates and maintains the Qdrant vector store. Two main pipelines:

#### Full Indexing Pipeline (`jobs/indexing.py`)
```
TMDB API → Fetch media IDs + details (credits, keywords, providers, trailers)
  → PostgreSQL: Upsert media_ids mapping (tmdb_id ↔ imdb_id)
  → BM25: Fit model on corpus, save vocab with stable indices
  → Qdrant: Create collection (dense + sparse vectors, payload indexes)
  → Chunked processing: format_embedding_text → dense embed → BM25 sparse → batch upsert
```

#### Rating Enrichment Pipeline (`core/rating_enrichment.py`)
- **Daily**: Recent releases → OMDb (RT score, Metascore, awards) → sync to Qdrant
- **Weekly**: Download IMDb dataset → upsert ratings → OMDb enrichment → sync to Qdrant

#### Shared Encoding Contract
Both the pipeline (index-time) and the API (query-time) share critical code from `packages/python/`:
- **`reelix_retrieval/bm25_tokenizer.py`**: Unified BM25 tokenizer (regex: `[a-z0-9]+` + stopwords + Porter stemming)
- **`reelix_retrieval/text_formatting.py`**: `format_embedding_text()` defines the text format the embedding model was fine-tuned on
- **`reelix_core/config.py`**: Collection names, model names, vector dimensions

**Key files (pipeline-specific)**:
- `core/tmdb_client.py` - Async TMDB API client with retry/semaphore
- `core/embedding_pipeline.py` - Batch embedding + payload formatting
- `core/bm25_utils.py` - BM25 model fitting + sparse vector creation (index-time)
- `core/vectorstore_pipeline.py` - Qdrant collection creation + batch upsert with rating preservation
- `core/rating_enrichment.py` - IMDb/OMDb enrichment + Qdrant payload sync
- `core/media_ids_repo.py` - PostgreSQL media_ids mapping

### API Routes (apps/api/app/routers/)

#### Discovery Routes (`routers/discovery/`)
- **`explore.py`** - Agent-powered vibe search (`/discovery/explore`)
  - Streams SSE: started → opening → recs → done
  - Orchestrator plans quickly → streams opening_summary + active_spec
  - Background: executes recommendation tool + curator
  - Returns final recs with why URL for explanations
- **`for_you.py`** - Personalized feed endpoint (`/discovery/for-you`)
  - Taste profile-based recommendations
  - Streams SSE responses with batch recommendations
- **`telemetry.py`** - Logging and analytics endpoints
- **`_helpers.py`** - Shared utilities for SSE streaming and response helpers

#### Core Routes
- `routes_taste_profile.py` - User taste vector management
- `routes_watchlist.py` - Watchlist CRUD operations
- `routes_interactions.py` - User interaction tracking
- `routes_user_settings.py` - User preferences and settings

### Frontend Features (apps/web/src/features/)
- `discover/` - Discovery experiences
  - `explore/` - Agent-based conversational search page (`/explore`)
  - For-You personalized feed
- `agent/` - Agent chat interface components
- `taste_onboarding/` - User preference collection
- `watchlist/` - Saved items management

### Key Patterns
- **Agent Tools** (`reelix_agent/tools/`): Pluggable tool system with registry, validation, and execution
  - `recommendation_tool.py`: Terminal tool that runs pipeline → curator → returns final_recs
  - `base.py`: Tool spec, registry, and runner infrastructure
- **Recipes** (`reelix_recommendation/recipes.py`): Define retrieval configurations (depths, weights, fusion params)
- **Ticket Store**: Redis-based temporary storage for LLM prompts/candidates between request phases
- **State Store**: Redis-based session memory storage for multi-turn agent conversations
- **SSE Streaming**: Two-phase streaming
  1. Orchestrator streams opening summary (fast)
  2. Explanation agent streams individual "why" explanations (JSONL over SSE)

### Logging Systems (Supabase)

Two layered logging systems:

#### Layer 1: Recommendation Pipeline Logging (All Endpoints)
| Table | Purpose |
|-------|---------|
| `rec_queries` | One row per API request (query_id, filters, context) |
| `rec_results` | Pipeline scores per candidate (dense, sparse, final) |

#### Layer 2: Agent Decision Logging (Agent Endpoints Only)
| Table | Purpose |
|-------|---------|
| `agent_decisions` | Orchestrator mode routing, spec generation, LLM usage |
| `curator_evaluations` | Per-candidate fit scores (genre, tone, theme) and tier |
| `tier_summaries` | Aggregate tier stats and selection rule applied |

**Key files:**
- `reelix_logging/rec_logger.py` - `TelemetryLogger` class with all logging methods
- `scripts/Supabase/logger_tables_schema.sql` - Pipeline tables schema
- `scripts/Supabase/agent_tables_schema.sql` - Agent tables schema

**Query pattern for combined analysis:**
```sql
-- Join curator fits with pipeline scores
SELECT ce.*, rr.score_dense, rr.score_sparse, rr.score_final
FROM curator_evaluations ce
JOIN rec_results rr ON ce.query_id = rr.query_id AND ce.media_id = rr.media_id
WHERE ce.query_id = 'xxx';
```

## Environment Variables

Required in `apps/api/.env`:
```
QDRANT_ENDPOINT=
QDRANT_API_KEY=
SUPABASE_URL=
SUPABASE_API_KEY=
OPENAI_API_KEY=
REDIS_URL=
```

Required in `apps/data-pipeline/.env`:
```
QDRANT_ENDPOINT=
QDRANT_API_KEY=
OPENAI_API_KEY=
TMDB_API_KEY=
OMDB_API_KEY=
DATABASE_URL=          # PostgreSQL connection string
```

## TypeScript SDK Generation

The frontend uses a generated TypeScript SDK from the OpenAPI spec:
```bash
# From root
pnpm generate

# Or directly
cd packages/js/ts-sdk
pnpm generate
```

The spec lives in `packages/schemas/openapi.yaml`.

## Python Package Dependencies

Both `apps/api` and `apps/data-pipeline` depend on shared packages via `uv` editable installs:
- `reelix-core` from `packages/python` (config, types, shared constants)
- `reelix-discovery-agent-api-client` from `packages/py-sdk` (API only)

The data pipeline imports from shared packages for the encoding contract:
- `reelix_core.config` — collection names, model names, vector dimensions
- `reelix_retrieval.bm25_tokenizer` — unified BM25 tokenizer
- `reelix_retrieval.text_formatting` — embedding text + LLM context formatting

Pyright is configured via `pyrightconfig.json` at the root to resolve these paths.
