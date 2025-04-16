# 🎬 RAG Movie Recommender

An AI-powered movie recommendation app using Retrieval-Augmented Generation (RAG), built with LangChain, OpenAI embeddings/ LLM, QDrant vectorDB, and Gradio. Deployed on Hugging Face Spaces.

## 🌐 Live Demo

👉 [Check it out on Hugging Face Spaces](https://huggingface.co/spaces/yourusername/movie-recommender)

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

- **LangChain** – Retrieval-augmented generation framework
- **OpenAI** – Embedding model and chat LLM provider
- **QDrant** – Vector database with hybrid search capabilities
- **Gradio** – Web UI interface library
- **Hugging Face Spaces** – Deployment platform
- **QDrant Cloud** – Hosting vector dataset

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
├── app.py                  # Main frontend app
├── chatbot.py              # LangChain RAG logic and OpenAI LLM chatbot setup
├── retriever.py            # QDrant retriever logic
├── config.py               # Configurations for environment variables
├── .env.example            # Environment variable template
└── requirements.txt        # Python dependencies
```

---

## 📸 Screenshots

<!-- WIP -->

---

## 🧠 How It Works

1. User types a natural language query.
2. LangChain retrieves relevant movie chunks from QDrant using semantic and scalar filters.
3. OpenAI generates a recommendation with natural response based on retrieved content.
4. The app displays results through an interactive chatbot UI with Gradio.

---

## 📄 License

[MIT License](LICENSE)