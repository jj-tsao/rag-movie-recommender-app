# 🎬 Reelix AI – Personalized Movie & TV Show Recommendations

[![Netlify](https://img.shields.io/netlify/e21595f0-7eca-4fde-8136-5593fb2b5392?logo=netlify&label=Live%20Site)](https://reelixai.netlify.app/)
[![Retriever Model](https://img.shields.io/badge/HuggingFace-Retriever%20Model-blue?logo=huggingface)](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)
[![Intent Classifier](https://img.shields.io/badge/HuggingFace-Intent%20Classifier-blue?logo=huggingface)](https://huggingface.co/JJTsao/intent_classifier-distilbert)
[![Made with FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi)](https://jjtsao-rag-movie-api.hf.space/docs#/)
[![Built with React](https://img.shields.io/badge/Frontend-React-61dafb?logo=react)](https://reelixai.netlify.app/)
![License](https://img.shields.io/github/license/jj-tsao/rag-movie-recommender-app)




Reelix is an AI-native movie and TV recommendation platform that curates personalized suggestions based on mood, theme, and storytelling preferences in natural language. Built with a modern full-stack architecture (FastAPI, React/Vite, Tailwind CSS, Supabase), Reelix leverages advanced retrieval-augmented generation (RAG) pipeline and large language models to deliver rich, emotionally attuned viewing recommendations.

At its core, Reelix combines hybrid vector search (dense/semantic + sparse/BM25) using a fine-tuned SentenceTransformer model with real-time intent classification (DistilBERT) and LLM reasoning. The system embeds user queries into semantic and keyword-based representations, retrieves contextually relevant candidates from a vector database (Qdrant), and dynamically crafts markdown-rich recommendations with rationale, ratings, and trailers — streamed live to the frontend.

From vibe-aware querying and streaming output to reranking by narrative relevance, Reelix blends AI retrieval, ranking, and generation into a seamless cinematic discovery experience.

## 🌐 Live Product 

👉 Try it here: [**Reelix AI**](https://reelixai.netlify.app/)

## Preview

> 🎬 Reelix understands your vibe and curates markdown-rich suggestions, trailers, and rationale in real time.

<img src="https://github.com/user-attachments/assets/ef03a55a-b9b5-4136-8654-5d7fa3f4e97d" alt="Reelix Preview" width="100%" />


---
## 🔗 Related Projects

- 💬 [Data and Embedding Pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline)  
- 🏋️ [Training Dataset Builder](https://github.com/jj-tsao/rag-movie-training-pipeline)
- 🧠 [Fine-Tuned Retriver Model](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5) (`bge-base-en-v1.5` based)
- 🤖 [Fine-Tuned Intent Classifier Model](https://huggingface.co/JJTsao/intent-classifier-distilbert-moviebot) (`distilbert-base-uncased` based)
---

## 🧠 Features

- **Hybrid Retrieval + Reranking**:
  - Dense semantic search via fine-tuned SentenceTransformer (`bge-base-en-v1.5`-based)
  - Sparse keyword search leveraging BM25 (Best Match 25) algorithm
  - Reranked by a weighted score of: semantic, sparse, rating, and popularity
  - Real-time retrieval pipeline from cloud-based vector database (Qdrant)

- **FastAPI Backend**:
  - `/chat` endpoint with streaming response (`StreamingResponse`)
  - `/log/final_recs` endpoint for usage data logging (Supabase)
  - Embedded model warm-up and retriever setup on startup

- **React Frontend (Vite + Tailwind CSS)**:
  - Real-time streaming UI with styled movie/ tv show recommendation cards
  - Advanced filters: streaming providers, genres, release year
  - Rich, personalized recommendations with rating, poster, trailer, and rationale (why you might enjoy it)

- **LLM Integration**:
  - Intent classification: detect recommendation vs. general chat using custom-trained DistilBERT model
  - Retrieval model trained on a dataset of vibe-based natural language queries to emulate real-world discovery patterns
  - Contextual, vibe-aware recommendation streaming based on retrieved results

- **Logging (Supabase)**:
  - Query logging with session, device, and intent metadata
  - Result logs: dense/sparse/reranking score breakdown per media item
  - Final selection and reasoning logging

---

## 🚀 Tech Stack

| Layer        | Tech                     |
|-------------|--------------------------|
| Frontend               | React + Vite + Tailwind CSS + ShadCN UI + TypeScript |
| Backend                | FastAPI (Python 3.13) + Docker                       |
| Intent Classification  | DistilBERT (fine-tuned `distilbert-base-uncased`)    |
| Embedding/ Retrieval   | SentenceTransformers (fine-tuned `bge-base-en-v1.5`) |
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
 |   ├── retrieval/
 |   |   ├── 📄 media_retriever.py # Hybrid retriever with dense + sparse + filters + reranking
 |   |   ├── 📄 retriever.py       # Retriever interface / logic binding vectorstore + reranker
 |   |   └── 📄 vectorstore.py     # Qdrant client + query interface
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

