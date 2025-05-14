# 🎬 RAG Movie & TV Recommender

An AI-powered recommendation system that delivers high-quality movie and TV show suggestions based on natural language queries, emotional tone, and metadata — using a fine-tuned BGE retriever model, dense/sparse hybrid vector search, scalar reranking, and Retrieval-Augmented Generation (RAG). Built with Sentence Transformers model, Best Match 25 (BM25) algorithm, Qdrant Vector DB, OpenAI/Anthropic API, Hugging Face, and Gradio. Deployed on Hugging Face Spaces.

## 🌐 Live Demo

👉 [Try the app on Hugging Face Spaces](https://huggingface.co/spaces/JJTsao/RAG_Movie_Recommendation_Assistant)

---

## 🔗 Related Projects

- 💬 Data and Embedding Pipeline: [GitHub: jj-tsao/rag-movie-embedding-pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline)  
- 🏋️ Training Dataset Builder: [rag-movie-training-pipeline](https://github.com/jj-tsao/rag-movie-training-pipeline)
- 🧠 Fine-Tuned Retriver Model (`bge-base-en-v1.5` based): [JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5](https://huggingface.co/JJTsao/fine-tuned_movie_retriever-bge-base-en-v1.5)

---
## 📌 Features

- 🧠 **RAG-based Recommendations** — Uses semantic retrieval + LLM reasoning to recommend titles based on story vibes, tone, and metadata.
- 💡 **Fine-Tuned BGE Retriever Model** — Custom trained `bge-base-en-v1.5` retriever on metadata and vibe-based queries for improved relevance and speed.
- 🎯 **Hybrid Search + Scalar Reranking** — Hybrid dense vector (Sentence Transformers) and sparse vector (BM25) similarity search, combined with scalar reranking by movie/show rating and popularity.
- 🎭 **Vibe-Aware Query Generation** — Model trained on emotional/mood-driven search phrases via LLMs to improve real-world matching behavior.
- 🧪 **Hard Negative Sampling** — Uses genre, keyword, and cast/crew-based contrastive samples to boost model robustness.
- 🔎 **Dynamic Filtering:** Refines recommendations through interactive filters by genres, streaming services, and release years
- ☁️ **Serverless Ready:** Retrieves up-to-date movie data from Qdrant Cloud vectorDB at runtime
- 🖼️ **Interactive UI** — Gradio chatbot UI with dynamic dropdowns and smooth streaming of LLM responses.

---

## 🧠 How It Works

1. **User Query**: You type a vibe-based prompt like _"Dark comedies with moral ambiguity and character-driven narrative"_.
2. **Dynamic Filter**: Apply additional filters for genres, streaming services, and release years to narrow down the result if prefer.
3. **Intent Detection**: A lightweight classifier determines if the prompt requests a recommendation.
4. **Embedding + Retrieval**: Query is embedded using a fine-tuned BGE model and BM25 algorithm; relevant chunks are retrieved from Qdrant.
5. **Reranking**: Retrieved results are scored using a weighted mix of semantic similarity, rating, and popularity.
6. **LLM Response**: LLM model generates a natural language final reply with insights, poster images, and reasoning.
7. **Conversation**: Continue refining the request or pivoting tone using the interactive chatbot.

---

## 🛠️ Tech Stack

- **SentenceTransformers** – Fine-tuned `bge-base-en-v1.5` retriever via _MultipleNegativesRankingLoss_
- **Best Match 25 (BM25)** - Sparse vector generation model
- **Qdrant** – Cloud-based vector store with hybrid search and scalar boosting
- **OpenAI** – Chat completions & training vibe query generation 
- **Anthropic Claude** – Intent classification
- **TMDB API** – Movie and TV data provider (see [Data pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline))
- **Hugging Face Hub** – Fine-tuned model hosting
- **Hugging Face Spaces** – App hosting
- **Gradio** – Streaming UI interface

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/rag-movie-recommender.git
cd rag-movie-recommender
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

Create a `.env` file:
```
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
QDRANT_API_KEY=your_qdrant_key
QDRANT_ENDPOINT=https://your-qdrant-endpoint_url
QDRANT_MOVIE_COLLECTION_NAME=your_qdrant_movie_collection_name
QDRANT_TV_COLLECTION_NAME=your_qdrant_tv_collection_name
```

### 4. Run the app locally

```bash
python app.py
```

---

## 📂 Project Structure

```
├── app.py                  # Main endtry point for the app
├── ui.py                   # Gradio UI with dynamic filters
├── chatbot.py              # Chat handler with intent detection & streaming
├── llm_services.py         # Embedding + chat model integration
├── rag_pipeline.py         # Retrieval and reranking logic
├── vectorstore.py          # Qdrant vector DB setup
├── config.py               # Environment config
└── requirements.txt        # Dependencies
```
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
## 📄 License

[MIT License](LICENSE)
