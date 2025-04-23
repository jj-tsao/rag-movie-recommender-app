# 🎬 RAG Movie Recommender

An AI-powered movie recommendation app using Retrieval-Augmented Generation (RAG), built with OpenAI Embedding/ Large Language Models (LLM), Qdrant vectorDB semantic search, The Movie Database (TMDB) API, and Gradio UI. Deployed on Hugging Face Spaces.

## 🌐 Live Demo

👉 [Check it out on Hugging Face Spaces](https://huggingface.co/spaces/JJTsao/RAG_Movie_Recommendation_Assistant)

---

## 🔗 Related Project

👉 Data Pipeline for Movie Fetching/Embedding: [GitHub: jj-tsao/rag-movie-embedding-pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline)

---
## 📌 Features

- 🧠 **Retrieval Augmented Generation (RAG):** Combines real-time vector search and LLM for intelligent recommendations and responses
- 🎯 **Hybrid Search & Reranking Pipeline:** Recommends movies based on natural language input combining semantic search and reranking by scalar metata (rating, popularity)
- 🔎 **Interactive Filtering:** Refines movie recommendation with filters based on user's input (genres, streaming services, release years)
- ☁️ **Serverless Ready:** Retrieves up-to-date movie data from Qdrant Cloud vectorDB at runtime
- 📊 **Dynamic Search UI:** Built with Gradio for fast and interactive querying

---

## 🛠️ Tech Stack

- **OpenAI** – LLM embedding and chat model provider
- **Anthropic** - Alternative LLM chat model provider
- **Qdrant** – Cloud-based vector database for retrieval
- **Gradio** – Web app UI library
- **TMDB API** – Movie data API provider (see [Data pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline))
- **Hugging Face Spaces** – Deployment platform

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
QDRANT_API_KEY=your_qdrant_key
QDRANT_ENDPOINT=https://your-qdrant-endpoint_url
QDRANT_COLLECTION_NAME=your_qdrant_collection_name
```

### 4. Run the app locally

```bash
python app.py
```

---

## 📂 Folder Structure

```
├── app.py                  # Main startup point for the app
├── ui.py                   # Frontend UI rendering with Gradio
├── chatbot.py              # LLM chatbot and intent classification setup
├── rag-pipeline.py         # Movie data retrieval and reranking pipeline
├── llm_utils.py            # OpenAI/Anthropic LLM utility functions
├── vectorestore.py         # Qdrant vector store utility functions
├── config.py               # Configurations for environment variables
└── requirements.txt        # Python dependencies
```

---

## 🧠 How It Works

1. User types a natural language query and apply optional filters (genres, streaming services, release years).
2. App retrieves relevant movie chunks from Qdrant, and reranks the results based on rating and popularity scores.
3. OpenAI generates a recommendation with natural language response based on retrieved content.
4. App displays results through an interactive chatbot UI with Gradio.
5. User contintues the conversation to refine the result or ask for new recommendations.

---

## 📄 License

[MIT License](LICENSE)
