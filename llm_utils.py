from openai import OpenAI
from anthropic import Anthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY

EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI model for query text embeddings
OPENAI_MODEL = "gpt-4o-mini"  # OpenAI model for intent classification and chat completions
ANTHROPIC_MODEL = "claude-3-haiku-20240307"  # Anthropic model for chat completions

SYSTEM_PROMPT = """
You are a professional film curator and critic. Your role is to analyze the user's preferences and recommend high-quality films using the provided context. 
Focus on: 

- Artistic merit and storytelling 
- Genres, themes, and tone
- Popularity, IMDB ratings, and Rotten Tomatoes ratings

Provide a brief explanation of why the user might enjoy each movie. Include IMDB rating, Rotten Tomatoe ratings, and movie poster. Answer with authority and care. Respond in markdown.
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
        {"role": msg["role"], "content": msg["content"]} for msg in history[-max_turns * 2:]  # user + assistant per turn. Only includes role and content.
    ]


def classify_intent(user_input: str) -> bool:
    system_prompt = "You are a helpful assistant that detects whether a message asks for movie recommendations. Respond only with 'yes' or 'no'."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Message: {user_input}"}
    ]

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0,
    )

    reply = response.choices[0].message.content.strip().lower()
    return "yes" in reply
    

def call_chat_model_openai(history, user_message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += build_chat_history(history or [])
    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


# Alternative LLM for chat completions using Anthropic API.
def call_chat_model_anthropic(history, user_message: str) -> str:  
    messages = []
    messages += build_chat_history(history or [])
    messages.append({"role": "user", "content": user_message})
    
    response = anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        system=SYSTEM_PROMPT,
        messages=messages,
        max_tokens=1000,
        temperature=0.7
    )
    return response.content[0].text.strip()
