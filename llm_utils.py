from openai import OpenAI
from config import OPENAI_API_KEY

openai_client = OpenAI(api_key = OPENAI_API_KEY)

def classify_intent(user_input: str) -> bool:
    system_prompt = "You are a helpful assistant that detects whether a message asks for movie recommendations. Respond only with 'yes' or 'no'."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Message: {user_input}"}
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0,
    )

    reply = response.choices[0].message.content.strip().lower()
    return "yes" in reply


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