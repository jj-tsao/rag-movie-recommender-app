from sentence_transformers import SentenceTransformer
import torch
from openai import OpenAI
from anthropic import Anthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY

# === LLM Config ===
EMBEDDING_MODEL = "JJTsao/fine-tuned_movie_retriever-all-mpnet-base-v2"  # Fine-tuned sentence transfomer model for query embedding 
OPENAI_MODEL = "gpt-4o-mini"  # LLM for chat completions
ANTHROPIC_MODEL = "claude-3-5-haiku-latest"  # Lighter Antrhopic model for intent classification
_sentence_model = None  # Not loaded at import time

# === Clients ===
openai_client = OpenAI(api_key = OPENAI_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

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
            EMBEDDING_MODEL,
            device="cuda" if torch.cuda.is_available() else "cpu"
        )

        print("🔥 Model '{EMBEDDING_MODEL}' loaded. Performing GPU warmup...")

        # Realistic multi-sentence warmup to trigger full CUDA graph
        warmup_sentences = [
            "A suspenseful thriller with deep character development and moral ambiguity.",
            "Coming-of-age story with emotional storytelling and strong ensemble performances.",
            "Mind-bending sci-fi with philosophical undertones and high concept ideas.",
            "Feel-good comedy about friendship, growth, and second chances."
        ]
        _ = _sentence_model.encode(warmup_sentences, show_progress_bar=False)
        print("🚀 Embedding model fully warmed up.")

    return _sentence_model


def embed_text(text: str) -> list[float]:
    model = load_sentence_model()
    return model.encode(text).tolist()


def build_chat_history(history: list, max_turns: int = 5) -> list:
    return [
        {"role": msg["role"], "content": msg["content"]} for msg in history[-max_turns * 2:]  # User + assistant per turn. Only includes role and content.
    ]



def classify_intent(user_input: str) -> bool:
    system_prompt = "You are a helpful assistant that detects whether a message asks for movie recommendations. Respond only with 'yes' or 'no'."

    response = anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Message: {user_input}"}],
        max_tokens=10,
        temperature=0
    )
    
    reply = response.content[0].text.strip().lower()
    return "yes" in reply
    

def call_chat_model_openai(history, user_message: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += build_chat_history(history or [])
    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
        stream=True
    )

    collected_chunks = []
    for chunk in response:
        if chunk.choices[0].delta.content:
            collected_chunks.append(chunk.choices[0].delta.content)
            yield "".join(collected_chunks)


# Alternative LLM option for chat completions with Anthropic API.
def call_chat_model_anthropic(history, user_message: str):
    messages = []
    messages += build_chat_history(history or [])
    messages.append({"role": "user", "content": user_message})
    
    accumulated_text = ""
    with anthropic_client.messages.stream(
        model=ANTHROPIC_MODEL,
        system=SYSTEM_PROMPT,
        messages=messages,
        max_tokens=1000,
        temperature=0.7
    ) as stream:
        for text in stream.text_stream:
            accumulated_text += text
            yield accumulated_text