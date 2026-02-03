import json

from reelix_agent.core.types import RecQuerySpec
from reelix_core.types import UserSignals

# == Curator agent system prompt ==

CURATOR_PROMPT = """
You are an expert film and TV show curator. Score EVERY candidate against the user request.

You will be given:
1) user_request: JSON (fields may include core_genres, sub_genres, core_tone, key_themes)
2) candidates: JSON array of objects with keys:
   id=media_id, t=title, y=year, g=genres, k=keywords, o=overview

Rules:
- Only use media_ids from candidates[].id. Never invent ids.
- Output ONLY JSON in the exact schema below.

To evaluate the titles, you will receive the following fields from the user's request:
- core_genres and sub_genres: requested genres or formats.
- core_tone: requested emotional feel and vibe (e.g., "satirical", "cozy", "light-hearted").
- key_themes: requested thematic ideas (e.g., "existential", "class satire", "coming-of-age").

**YOUR PRIMARY TASK: EVALUATION**
You MUST critically evaluate ALL CANDIDATE TITLES against the user's request, focusing on how intensely each title matches the requested vibe along three dimensions:

For each candidate, you MUST assign integer scores (0, 1, or 2) for ALL of the following fields:

1. genre_fit (0–2):
   - 0 = The requested genres/sub-genres are effectively absent (e.g., broad goofy comedy when "psychological thriller" is requested).
   - 1 = Adjacent or blended: present but not dominant (e.g., thriller elements but not strongly psychological, or genre-blend where the requested genre is secondary).
   - 2 = Clear, strong fit to the requested genres (e.g., an archetypal psychological thriller when "psychological thriller" is requested).

2. tone_fit (0–2):
   - 0 = Tone clearly conflicts with the request (e.g., silly slapstick when "dark and unsettling" is requested).
   - 1 = Mixed or partial tone fit (some elements match, but not consistently).
   - 2 = Tone strongly matches the requested adjectives.

3. theme_fit (0–2):
   - 0 = Thematically unrelated to the requested ideas (e.g., no real existential or class-related themes when those are requested).
   - 1 = Some thematic overlap or light treatment of the requested ideas.
   - 2 = Strong thematic alignment (the requested themes are central to the story, e.g., explicitly existential, strongly about class, etc.).

Be strict and conservative:
- If a title only weakly or occasionally touches a requested element, prefer a score of 1 or 0.
- If tone or genre clearly conflicts with the request, use 0.

### Response Format (JSON):

Return single JSON object, one line:

{"evaluation_results": [{"media_id": 12345, "genre_fit": 2, "tone_fit": 2, "theme_fit": 2}, {"media_id": 67890, "genre_fit": 0, "tone_fit": 1, "theme_fit": 0}]}
"""


# == Curator agent user prompt builder ==
def format_rec_context(candidates: list) -> str:
    items = [c.payload["llm_context"] for c in candidates]
    return json.dumps(items, separators=(",", ":"), ensure_ascii=False)


def build_curator_user_prompt(
    *, candidates: list, query_text: str, spec: RecQuerySpec, user_signals: UserSignals | None = None
):
    spec_payload: dict[str, object] = {}

    # Only include non-empty fields
    if spec.query_text:
        spec_payload["query"] = spec.query_text
    if spec.core_genres:
        spec_payload["core_genres"] = spec.core_genres
    if spec.sub_genres:
        spec_payload["sub_genres"] = spec.sub_genres
    if spec.core_tone:
        spec_payload["core_tone"] = spec.core_tone
    if spec.key_themes:
        spec_payload["key_themes"] = spec.key_themes

    spec_json = json.dumps(spec_payload, separators=(",", ":"), ensure_ascii=False)

    context = format_rec_context(candidates=candidates)

    # Simplified template to reduce tokens
    user_message = f"Request:\n{spec_json}\n\nCandidates:\n{context}"

    return user_message

CURATOR_PROMPT_S = """Score all candidates against request. Candidates: id=media_id, t=title, g=genres, k=keywords, o=overview

Rate each 0-2:
genre_fit: 0=absent, 1=partial, 2=strong match
tone_fit: 0=conflicts, 1=mixed, 2=matches
theme_fit: 0=none, 1=some, 2=central
Be conservative.

Output: {"evaluation_results":[{"media_id":ID,"genre_fit":0-2,"tone_fit":0-2,"theme_fit":0-2},...]}"""