import time

import torch
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL, OPENAI_MODEL, OPENAI_API_KEY

# === LLM Config ===
_sentence_model = None  # Not loaded at import time

# === Clients ===
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# === System Prompt ===
SYSTEM_PROMPT = """
You are a professional film curator and critic. Your role is to analyze the user's preferences and recommend high-quality films or TV shows using the provided context. Do not seek film or tv show options outside of the list provided to you.
Focus on: 

- Artistic merit and storytelling 
- Genres, themes, and tone
- Popularity, IMDB ratings, and Rotten Tomatoes ratings

Provide a brief explanation of why the user might enjoy each movie or tv series. Include IMDB rating, Rotten Tomatoe ratings, and a poster. Answer with authority and care. Respond in markdown.
"""


def load_sentence_model():
    global _sentence_model
    if _sentence_model is None:
        print("⏳ Loading embedding model...")
        _sentence_model = SentenceTransformer(
            EMBEDDING_MODEL, device="cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"🔥 Model '{EMBEDDING_MODEL}' loaded. Performing GPU warmup...")

        # Realistic multi-sentence warmup to trigger full CUDA graph
        warmup_sentences = [
            "A suspenseful thriller with deep character development and moral ambiguity.",
            "Coming-of-age story with emotional storytelling and strong ensemble performances.",
            "Mind-bending sci-fi with philosophical undertones and high concept ideas.",
            "Recommend me some comedies.",
        ]
        _ = _sentence_model.encode(warmup_sentences, show_progress_bar=False)
        time.sleep(0.5)
        _ = _sentence_model.encode(warmup_sentences, show_progress_bar=False)
        print("🚀 Embedding model fully warmed up.")

    return _sentence_model


def embed_text(text: str) -> list[float]:
    model = load_sentence_model()
    return model.encode(text).tolist()


def build_chat_history(history: list, max_turns: int = 5) -> list:
    return [
        {"role": msg.role, "content": msg.content}
        for msg in history[-max_turns * 2:]
    ]



def call_chat_model_openai(history, user_message: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += build_chat_history(history or [])
    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, temperature=0.7, stream=True
    )

    for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
