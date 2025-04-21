# 🎬 RAG Movie Recommender

An AI-powered movie recommendation app using Retrieval-Augmented Generation (RAG), built with OpenAI Embedding/ Large Language Models, QDrant vectorDB, TMDI API, and Gradio. Deployed on Hugging Face Spaces.

## 🌐 Live Demo

👉 [Check it out on Hugging Face Spaces](https://huggingface.co/spaces/JJTsao/RAG_Movie_Recommendation_Assistant)

---

## 🔗 Related Project

👉 Pipeline for Data Fetching/Embedding: [GitHub: jj-tsao/rag-movie-embedding-pipeline](https://github.com/jj-tsao/rag-movie-embedding-pipeline)

---
## 📌 Features

- 🎯 **Hybrid Semantic Search + Scalar Boosting:** Recommend movies based on natural language queries using hybrid semantic search and scalar value boosting (e.g., rating, popularity)
- 🔎 **Scalar Value Filtering:** Refine movie recommendations based on filter input from users (e.g., genres, streaming services, release years)
- 🧠 **RAG with LangChain + QDrant:** Combines vector search and LLM for intelligent responses
- 📊 **Dynamic Search UI:** Built with Gradio for fast and interactive querying
- ☁️ **Serverless Ready:** Loads vector DB from QDrant Cloud at runtime

---

## 🛠️ Tech Stack

- **OpenAI** – Embedding model and chat LLM provider
- **QDrant** – Vector database with hybrid search capabilities
- **Gradio** – Web UI interface library
- **Hugging Face Spaces** – Deployment platform
- **QDrant Cloud** – Hosting vector dataset
- **TMDB API** – Provider of movie data

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
├── chatbot.py              # LLM chatbot, memory, and context retrieval setup
├── rag-pipeline.py         # Movie data retrieval and reranking logic
├── llm_utils.py            # OpenAI embedding & LLM utility functions
├── vectorestore.py         # QDrant client utily function
├── config.py               # Configurations for environment variables
├── .env.example            # Environment variable template
└── requirements.txt        # Python dependencies
```

---

## 🧠 How It Works

1. User types a natural language query and apply optional filters (genres, streaming services, release year).
2. The app retrieves relevant movie chunks from QDrant and reranks the results based on rating and popularity score.
3. OpenAI generates a recommendation with natural response based on retrieved content.
4. The app displays results through an interactive chatbot UI with Gradio.
5. User can contintue the conversation to refine the results or ask for new recommendation

---

## 📄 License

[MIT License](LICENSE)
