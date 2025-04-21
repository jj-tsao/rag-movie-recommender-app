from openai import OpenAI
from config import OPENAI_API_KEY

openai_client = OpenAI(api_key = OPENAI_API_KEY)


def embed_text(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def call_chat_model(messages: list[dict]) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


def build_chat_history(history: list, max_turns: int = 5) -> list:
    return history[-max_turns*2:]  # user + assistant per turn