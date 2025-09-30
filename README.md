# 🎬 Reelix AI – Personalized Movie & TV Show Recommendations

[![Netlify](https://img.shields.io/badge/Live%20Site-Netlify-42b883?logo=netlify)](https://reelixai.netlify.app/)
[![Retriever Model](https://img.shields.io/badge/Retriever%20Model-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)
[![Intent Classifier](https://img.shields.io/badge/Intent%20Classifier-HuggingFace-blue?logo=huggingface)](https://huggingface.co/JJTsao/intent-classifier-distilbert-moviebot)
[![Made with FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://jjtsao-rag-movie-api.hf.space/docs#/)
[![Built with React](https://img.shields.io/badge/Frontend-React-61dafb?logo=react)](https://reelixai.netlify.app/)
![License](https://img.shields.io/github/license/jj-tsao/rag-movie-recommender-app)


[Reelix](https://reelixai.netlify.app/) is an AI‑native discovery agent that turns a vibe‑style natural language query into cinematic recommendations. 

Built with a modern full-stack architecture (FastAPI, React/Vite, Qdrant Vector DB, Supabase), Reelix leverages advanced retrieval-augmented generation (RAG) pipeline and large language models to deliver rich, emotionally attuned viewing recommendations.

It combines hybrid search (dense/semantic + sparse/BM25) using fine-tuned SentenceTransformer retriever (BGE), with cross‑encoder reranker (BERT), real-time intent   classification (DistilBERT), and LLM reasoning to dynamically craft markdown-rich recommendations with rationale, ratings, and trailers, streaming live to the frontend. 

---

## ✨ What’s New (Recommendation Pipeline v2)

Reelix now runs a 4‑stage recommendation pipeline with a fine‑tuned [Cross‑Encoder (CE) reranker](https://github.com/jj-tsao/rag-movie-reranker-training-pipeline/tree/main):

1. Base Fusion (RRF) – Build a candidate pool by fusing top‑K results from dense semantic search and sparse BM25 (reciprocal‑rank fusion, k=60).

2. Metadata Rerank – Score candidates with a weighted model: dense 0.60 + sparse 0.15 + rating 0.15 + popularity 0.10. Ratings use a Bayesian prior and popularity is log‑scaled with media‑type anchors (movie vs TV) for robust normalization across tails.

3. Cross‑Encoder Rerank (CE) – Re‑score the dense top‑30 with a fine‑tuned BERT‑based CE on (query, doc) pairs, then produce a CE order.

4. Final Fusion (RRF) – Fuse (top metadata IDs) vs (top CE IDs) to get a stable final list that benefits from both content signals and learned pairwise relevance.

- CE fallback: if the CE model is unavailable, the system gracefully returns the metadata‑reranked list.

---

## 🌐 Live Product 

👉 Try it here: [**Reelix AI**](https://reelixai.netlify.app/)

## Preview

> Reelix understands your vibe and curates markdown-rich suggestions, trailers, and rationale in real time.

<img src="https://github.com/user-attachments/assets/ef03a55a-b9b5-4136-8654-5d7fa3f4e97d" alt="Reelix Preview" width="100%" />


---
## 🔗 Related Projects

- [Reranker Training](https://github.com/jj-tsao/rag-movie-reranker-training-pipeline/tree/main)
- [Trained Cross-Encoder Reranker](https://huggingface.co/JJTsao/movietv-reranker-cross-encoder-base-v1) (`bert-base-uncased` backbone)
- [Retriever Training](https://github.com/jj-tsao/rag-movie-training-pipeline)
- [Fine-Tuned Retriever Model](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5) (`bge-base-en-v1.5` based)
- [Fine-Tuned Intent Classifier Model](https://huggingface.co/JJTsao/intent-classifier-distilbert-moviebot) (`distilbert-base-uncased` based)
- [Data and Embedding Pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline)
---

## ✨ Features

- **Hybrid Retrieval + Reranking**:
  - Dense semantic retrieval via fine‑tuned bge-base-en-v1.5
  - Sparse keyword retrieval via BM25 (trained over curated "embedding_text")
  - Metadata rerank with Bayesian quality + log popularity anchors
  - Fine‑tuned Cross‑Encoder reranker (BERT backbone) for pairwise relevance
  - Double‑RRF fusions for robustness (pre‑pool + final fusion)

- **FastAPI Backend**:
  - `/chat` streams markdown with structured tokens for the UI
  - `/log/final_recs` stores final selections & why‑summaries to Supabase
  - On‑startup warmups for embedder, intent classifier, BM25, and CE

- **React Frontend (Vite + Tailwind CSS)**:
  - Real‑time card streaming; trailer, ratings, genres, why‑you’ll‑like‑it
  - Advanced filters (providers/genres/year) with accessible UI controls
  - Rich, personalized recommendations with rating, poster, trailer, and rationale (why you might enjoy it)

- **LLM Integration**:
  - Intent classifier (DistilBERT) to route **recommendation vs chat**
  - Retrieval model trained on a dataset of vibe-based natural language queries to emulate real-world discovery patterns
  - Contextual, vibe-aware recommendation streaming based on retrieved results

- **Logging (Supabase)**:
  - Query/result logs with **dense/sparse/metadata/CE/final** traces
  - Session, device, and filter metadata for analysis

---
## 🏗️ Pipeline Architecture (High‑Level)

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
| Frontend               | React + Vite + Tailwind CSS + ShadCN UI + TypeScript |
| Backend                | FastAPI (Python 3.13) + Docker                       |
| Intent Classification  | DistilBERT (fine-tuned `distilbert-base-uncased`)    |
| Embedding/ Retrieval   | SentenceTransformers (fine-tuned `bge-base-en-v1.5`) |
| Reranking | **Cross‑Encoder (BERT)** + Metadata scoring + **RRF** |
| Sparse Search          | BM25 (Best Match 25) via `rank_bm25`                 |
| Tokenization           | NLTK (Natural Language Toolkit)                      |
| Vector DB              | Qdrant (hybrid search)                               |
| Chat Completion        | OpenAI API                                           |
| Model Hosting          | Hugging Face Hub                                     |
| Storage/Logs           | Supabase                                             |
| Movie Metadata         | TMDB (The Movie Database) API                        |
| Deployment             | Frontend: Netlify, Backend: Hugging Face Spaces      |

---

## 📚 Sample Query Flow

1. User enters a vibe-based prompt (e.g., _“Mind-bending sci-fi with existential themes”_)
2. User selects advanced fitlers if desired (optional)
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

## 📁 Project Structure

```
📦 backend/
 ├── 📄 main.py                    # Entrypoint for FastAPI server
 ├── 📄 Dockerfile                 # Docker container setup for API deployment
 ├── 📄 requirements.txt           # Python dependencies for backend
 ├── app/
 |   ├── api/
 |   |   ├── 📄 api_routes.py      # Defines REST API endpoints (chat, logging, etc.)
 |   |   └── 📄 schemas.py         # Pydantic request/response schemas
 |   ├── core/
 |   |   ├── 📄 bootstrap.py       # Initializes retriever and intent classifier models at startup
 |   |   └── 📄 config.py          # Environment config, keys, and constants
 |   ├── llm/
 |   |   ├── 📄 custom_models.py   # Loads SentenceTransformer, DistilBERT, and BM25 models
 |   |   └── 📄 llm_completion.py  # Handles OpenAI GPT streaming completions
 │   ├── rec_pipeline/
 │   │   └── recommend.py          # 4‑stage pipeline (RRF → metadata → CE → RRF)
 │   ├── ranking/
 │   │   ├── metadata.py           # Bayesian rating; log‑pop anchors; weights
 │   │   ├── cross_encoder_reranker.py  # CE wrapper (batching, fp16 CUDA)
 │   │   └── rrf.py                # Reciprocal‑rank fusion util
 |   ├── retrieval/
 │   │   ├── base_retriever.py  # Qdrant dense/sparse search; payloads
 │   │   ├── query_encoder.py   # Dense + BM25 sparse for user query
 │   │   ├── filter_builder.py  # Providers/genres/year filters → Qdrant Filter
 │   │   └── vectorstore.py     # Qdrant client + connection
 |   ├── services/          
 |   |   ├── 📄 chatbot.py         # Main chat function: embeds, retrieves, calls LLM
 |   |   └── 📄 usage_logger.py    # Logs queries and results to Supabase
 └── Data/
     ├── bm25_files/               # Saved BM25 model and vocabulary joblib files
     └── nltk_data/                # NLTK tokenizers and stopwords used in text preprocessing

📦 frontend/
 ├── 📄 index.html                # HTML entry point (linked to Vite build)
 ├── public/                      # Static assets like icons, logos, and favicons
 ├── src/
 |   ├── 📄 main.tsx              # React/Vite app entry point
 |   ├── 📄 App.tsx               # Top-level React app wrapper
 |   ├── 📄 api.tsx               # Defines client-side API calls (chat, logging)
 |   ├── 📄 index.css             # Tailwind and global styles
 |   ├── components/
 |   |   ├── 📄 ChatBox.tsx       # Streams and renders API responses, manages state
 |   |   ├── 📄 Filters.tsx       # Genre/provider/year filter controls
 |   |   ├── 📄 FloatingActionButton.tsx # Re-query CTA when scrolled away
 |   |   ├── 📄 Home.tsx          # Main user interface with input + filters + results
 |   |   ├── 📄 MovieCard.tsx     # Stylized result card with poster, ratings, trailer, and reasoning
 |   |   ├── 📄 MultiSelectDropdown.tsx # Generic multiselect dropdown component
 |   |   ├── 📄 TopNav.tsx        # Logo, theme toggle, and nav bar
 |   |   └── 📄 YearRangeSlider.tsx # Year range slider for release filtering
 |   ├── ui/                      # ShadCN UI components and Tailwind primitives
 |   ├── lib/                     # Shared helpers, hooks, or custom utilities
 |   ├── types/
 |   |   ├── 📄 css.d.ts          # CSS module typing (for Tailwind/shadcn interop)
 |   |   └── 📄 types.ts          # Global TypeScript interfaces
 |   └── utils/
 |       ├── 📄 checkScores.ts    # Helpers for rating availability checks
 |       ├── 📄 detectDevice.ts   # Captures device platform + user agent metadata
 |       ├── 📄 parseMarkdown.ts  # Extracts structured movie blocks from API response
 |       └── 📄 session.ts        # Generates unique session/query IDs for logging
 ├── 📄 components.json           # ShadCN component registry (used by CLI)
 ├── 📄 eslint.config.json        # ESLint rules for code quality
 ├── 📄 netlify.toml              # Netlify deploy/build configuration
 ├── 📄 package-lock.json         # Exact NPM dependency versions
 ├── 📄 package.json              # Frontend dependencies, scripts, and metadata
 ├── 📄 tsconfig.app.json         # TypeScript config scoped to app source
 ├── 📄 tsconfig.json             # Root TS config with compiler options
 ├── 📄 tsconfig.node.json        # TypeScript config for Node scripts/tools
 ├── 📄 vite-end.d.ts             # Vite global types and env var typings
 └── 📄 vite.config.ts            # Vite build/dev server configuration
```

---

## 🧪 Example Prompts

- _"Slow-burn thrillers with morally complex characters and rich atmosphere"_
- _"Feel-good dramas with emotional storytelling and family themes"_
- _"Visually stunning sci-fi with existential and philosophical undertones"_

---

## 📦 Development Setup

### 1. Backend (FastAPI)

```bash
# Install dependencies
pip install -r requirements.txt

# Set env variables (.env or export directly)
QDRANT_API_KEY=...
OPENAI_API_KEY=...
SUPABASE_API_KEY=...

# Run the server
uvicorn main:app --reload --port 7860
```

### 2. Frontend (React + Vite)

```bash
# Install dependencies
npm install

# Run local dev server
npm run dev

# For production build
npm run build
```

### 3. Environment Variables

For React frontend:
```ts
const BASE_URL = import.meta.env.VITE_BACKEND_URL;
```

Define `VITE_BACKEND_URL` in Netlify’s UI or `.env`.

---

## 📝 License

[MIT](LICENSE)

