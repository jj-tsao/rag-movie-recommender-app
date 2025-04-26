from openai import OpenAI
from anthropic import Anthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY

EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI model for query text embedding
OPENAI_MODEL = "gpt-4o-mini"  # OpenAI model for chat completion
ANTHROPIC_MODEL = "claude-3-haiku-20240307"  # Lighter and faster model for for intent classification

SYSTEM_PROMPT = """
You are a professional film curator and critic. Your role is to analyze the user's preferences and recommend high-quality films or TV shows using the provided context. 
Focus on: 

- Artistic merit and storytelling 
- Genres, themes, and tone
- Popularity, IMDB ratings, and Rotten Tomatoes ratings

Provide a brief explanation of why the user might enjoy each movie or tv series. Include IMDB rating, Rotten Tomatoe ratings, and a poster. 
Do not seek film or tv show options outside of the list provided to you. Answer with authority and care. Respond in markdown.
"""

openai_client = OpenAI(api_key = OPENAI_API_KEY)
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)


def embed_text(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding


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