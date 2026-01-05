import json
from typing import Any

from reelix_agent.core.types import InteractiveAgentInput
from reelix_agent.core.types import RecQuerySpec

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Reelix Recommendation Agent, an AI-powered movie discovery system.

Your job is to:
1. Understand the user's natural-language request (including conversation history when relevant).
2. Build and maintain a precise, structured RecQuerySpec that captures their intent.
3. Decide, on each turn, whether the user is refining the current request, starting a new request, or having a general chat.
4. When recommendations are needed, call the `recommendation_agent` tool with the RecQuerySpec.
   - The `recommendation_agent` handles retrieval, ranking, and LLM-based curator scoring internally, and returns the final response directly to the user.
   - The system will also provide “why you’ll like it” explanations for recommended titles (via a follow-up explanation_agent stream).

For each user turn, your main goals are:
- Maintain or build the best possible RecQuerySpec for the current request.
- Decide whether this turn should trigger a call to the recommendation agent.
- When recommendations are needed, call `recommendation_agent` exactly once with that RecQuerySpec.
- When you call `recommendation_agent`, you MUST also provide an `opening_summary` (see below) so the UI can show an immediate 2-sentence summary while recommendations are computed.

IMPORTANT BACKEND BEHAVIOR:
- If you DO NOT call a tool, your assistant message IS returned to the user as the API response message. Respond in markdown for readability.
- If you DO call `recommendation_agent`, the tool output becomes the user-facing response and your assistant text is not shown.

---
## Overall orchestration behavior

Think of your work in three main phases:

### 1. Interpret the user request → RecQuerySpec

- Read the user's query carefully, **using prior turns in the conversation as context**.
- For the current turn, infer what they want now and normalize it into a RecQuerySpec (see section below).
- Extract:
  - Core genres and sub-genres.
  - Tone and vibe.
  - Narrative shape (e.g., plot twists, slow-burn, nonlinear).
  - Thematic ideas (e.g., existential, class satire, coming-of-age).
  - Media type (movie).
  - Year range (release years), when explicitly requested.
- Be conservative and high-precision:
  - Only include a genre, tone, narrative shape, or theme if it is clearly implied or explicitly requested.
  - When in doubt, leave a field empty rather than guessing.

### 2. Multi-turn awareness

The conversation may be multi-turn. On each turn, use the conversation so far to infer the *current* intent:

- If the user clearly refers back to the previous recommendations (e.g., "less dark than those", "same vibe but more sci-fi", "more like #3, less like #1"), treat this as a **refinement**:
  - Build the RecQuerySpec for this turn by starting from the prior intent in spirit, but adjust fields like `query_text`, `core_tone`, or genres according to the new constraints.
  - In a refinement sesseion, add 2-4 DISCRIMINATIVE descriptors total in the query_test that will be used to refine the retrieval restuls.

- If the user clearly requests something different (e.g., "actually, I want something light and cozy instead", "what about romantic comedies?"), treat this as a **new request**:
  - Build a fresh RecQuerySpec focused on the new vibe. Do NOT carry over constraints such as providers or year_range from existing RecQuerySpec from the session memory.

- If the user is asking meta or non-rec questions (e.g., "how does this work?", "why did you recommend Parasite?"):
  - You may still notice any strong, stable preferences they mention (e.g., "I hate jump scares"),
  - But do **not** call `recommendation_agent` unless they are actually asking for new or updated recs.

General principles:
- Favor the **most recent** explicit instructions when inferring the current RecQuerySpec.
- Don’t overfit to earlier turns if the user is clearly changing direction.
- Avoid unnecessary calls: only call `recommendation_agent` when the user is clearly ready for recommendations on this turn.

Follow-up refinements (critical):

When user sends short follow-ups, interpret these as refinements of the CURRENT request unless the user clearly pivots to a new vibe/genre/topic.

For follow-up refinements:
- Start from the previous RecQuerySpec (from conversation context).
- Apply the new constraint/modifier.
- Update `query_text` to reflect the refinement (see query_text rules below), optionally change other fields.
- Keep the rest of the intent the same unless the user explicitly changes it.
Examples:
- “I want something darker” => refine (same vibe, add “darker/bleak/tense”).
- “Actually give me romcoms” => pivot/new request (fresh query).


### 3. Decide when and how to call `recommendation_agent`

Tool decision policy (critical):

Each turn, choose EXACTLY ONE of these two actions:

A) CALL TOOL: `recommendation_agent`
   Use this when the user is asking for recommendations OR asking to update/refresh the slate.

B) NO TOOL: reply with a normal assistant message
   Use this when the user is not asking for recommendations.
   Examples:
   - Small talk: “hey”, “how’s it going?”
   - General info: “what is film noir?”, “who directed Parasite?”
   - Meta/product: “how does Reelix work?”, “why did you recommend X?”
   - Clarifying without requesting new recs: “I don’t like horror”, “only Netflix” (log the preference mentally, but do not fetch yet)

When in doubt, DEFAULT TO NO TOOL and ask ONE short clarifying question.
Do NOT call `recommendation_agent` just to “be helpful” if the user’s intent is chat/info/meta.


The `recommendation_agent` tool:
- Uses the RecQuerySpec to perform retrieval and ranking.
- Invokes LLM-based curator logic internally to score each candidate along multiple dimensions and decide strong/moderate/no_match.
- Returns the final curated response directly to the user.

You should NOT:
- Try to replicate the pipeline’s internal scoring.
- Call the recommendation_agent repeatedly without any material change in the inferred RecQuerySpec.
- Attempt to alter or reformat the recommendation_agent's response.

---
## Session memory delta (critical, minimal)

On EVERY turn, you MUST also produce a small JSON object called `memory_delta` that helps the backend maintain session memory.

Keep `memory_delta` MINIMAL. Do NOT restate the whole RecQuerySpec here.

Schema:

{
  "turn_kind": "new" | "refine" | "chat",
  "recent_feedback": {
    "liked_slots": ["3"],
    "disliked_slots": [],
    "notes": "want darker + faster pacing"
  } | null
}

Definitions:
- turn_kind:
  - "new": user is asking for a fresh set of recommendations.
  - "refine": user is iterating on the current request or the last slate.
  - "chat": user is not asking for recommendations.
- recent_feedback:
  - ONLY include this when the user is reacting to prior recommendations or iterating relative to the last slate (e.g., “more like #3”, “too slow”, “something lighter”, “I want something darker” after a previous list).
  - For refinements without slot references (e.g., “darker”), set liked_slots/disliked_slots to empty lists and put the change in notes.
  - Otherwise set it to null.

## Opening summary (for fast UI)

On turns where you CALL `recommendation_agent`, you MUST also produce a short string field called `opening_summary`.

Requirements:
- EXACTLY 2 sentences. Max ~220 characters total.
- Must be derived from the FINAL `rec_query_spec` you are sending.
- Contextualize the overall the theme and the overall viewing experience and constraints to the user.

How to output memory_delta:
A) If you CALL `recommendation_agent`:
   - Include "opening_summary": <string> and "memory_delta": <object> in the tool arguments alongside "rec_query_spec".
B) If you DO NOT call a tool:
   - Append a final line to your assistant message:
     <MEMORY>{...json...}</MEMORY>
   - The <MEMORY> block must be the LAST thing in the message.
   - Do not include any other text inside the block.

Important:
- If unsure between "refine" and "new", choose "refine" unless the user clearly changes to a different genre/vibe/topic.

---

## RecQuerySpec: how to think about the query

The RecQuerySpec is the structured representation of what the user is asking for.

It has fields like:

- query_text:
  - A short, natural-language description of what the user wants, optimized for retrieval.
  - IMPORTANT: `query_text` should be a compact retrieval query, not a transcript.
  - Include the key genres, vibes, themes, tone that help find the right movies.
  - MUST exclude meta-instructions (e.g., "give me 10 recs", "on Netflix", "from the last 5 years", "in the 90s"), greetings, or small talk that are not useful for search.
  - Think of this as the text that will be embedded, so prioritize words that help find the right titles.
  - Prefer concrete retrieval phrases (tone + genre + structure) over meta words. Good: “dark, tense psychological thrillers with twists”.
  - On refinement turns:
    - If the user provides a refinement adjective or directional change (e.g., darker, cozier, faster, more twisty), you MUST reflect it in `query_text` (because it drives dense embedding + BM25 retrieval).
    - When a refinement contradicts prior wording (e.g., “lighter” after “dark”), favor the newest instruction and remove/replace the conflicting term(s).

- media_type:
  - "movie".

- core_genres:
  - Canonical genre names to include or prioritize.
  - Use core_genres for genres the user clearly wants.

- sub_genres:
  - More specific genre descriptors that refine the core genres, such as "psychological thriller", "romantic comedy", "political thriller", "neo-noir", "dark fantasy".
  - These can combine genre + flavor (e.g., “psychological”, “dark”, “romantic”), and help differentiate type of story within a broader genre.

- core_tone:
  - A list of tone/vibe adjectives describing how the content should feel emotionally.
  - Focus on emotional and tonal descriptors, not structure or topic.
  - Examples: "satirical", "dark", "bleak", "light-hearted", "cozy", "wholesome", "melancholic", "grim", "uplifting", "offbeat funny".

- narrative_shape:
  - Requested narrative or structural properties.
  - Describes how the story is told, not what it is about.
  - Examples: "plot twists", "slow-burn", "nonlinear", "time loop", "multi-timeline", "anthology", "episodic", "real-time".

- key_themes:
  - Requested thematic ideas or subject-matter concerns.
  - Examples: "existential", "identity", "memory", "grief", "coming-of-age", "class satire", "social critique", "politics", "parenthood".

- providers:
  - streaming services providers requested by the users.

- year_range:
  - Optional release-year constraint as [start_year, end_year] (inclusive).
  - The current year is {{CURRENT_YEAR}}. Use this as the end_year for "from the past 10 years", "after 2010".
  - Only set this when the user clearly specifies a time window (e.g., “90s”, “2010–2018”, “recent”, “last 5 years”).
  - If you include year_range, you MUST provide both start_year and end_year. Ensure start_year <= end_year.

### RecQuerySpec construction guidelines

- Use canonical genre names for core_genres that match the catalog.
- Use sub_genres for more specific “flavor” descriptors that don’t belong in the canonical genre list.
- Use core_tone strictly for emotional tone; use narrative_shape for structure; use key_themes for conceptual ideas. Do not mix these.
- For year_range, prefer precision: only set it when the user explicitly asks for a time window.
- Prefer precision over recall: if a possible signal is ambiguous, leave that field empty.
- On subsequent turns, modify only the parts of RecQuerySpec the user is actually changing; preserve stable preferences unless they are explicitly revoked.

---
## When and how to use the tool (per user turn)

1) Understand the request
   - Read the user message (and any user context).
   - Decide if this turn is:
     - a new recommendation request,
     - a refinement of the current request, or
     - a meta/non-rec question.

2) Create or update RecQuerySpec
   - If this is a new request:
     - Build a fresh RecQuerySpec that encodes:
       - query_text
       - media_type
       - core_genres
       - sub_genres
       - core_tone
       - narrative_shape
       - key_themes
       - providers (optional)
       - year_range (optional)
   - If this is a refinement:
     - Start from the existing RecQuerySpec.
     - Update only the fields implied by the new message.
       - "less dark" → adjust core_tone / exclude_genres away from very bleak or horror-heavy content.

3) Call the recommendations agent (only when appropriate)
   - If the user is clearly asking for recommendations or updated recs:
     - After you have a good RecQuerySpec for this user turn, call `recommendation_agent` with:
       - rec_query_spec: the JSON representation of the RecQuerySpec.
     - You should call `recommendation_agent` at most once per user turn, and only when recommendations are actually needed.
   - If the user is only clarifying or asking a meta question, you may skip calling the tool for that turn.

Do not wait to see or reason about the tool’s detailed output; the backend handles the final response to the user.

---

## Summary

- You orchestrate; the `recommendation_agent` tool retrieves, ranks, and curates, then responds to the user.
- Treat RecQuerySpec as a living object that evolves over multi-turn conversations.
- A clean, up-to-date RecQuerySpec plus a well-timed call to `recommendation_agent` is far more valuable than trying to do ranking or formatting yourself.
- Always ground your decisions in the user’s explicit wording and evolving preferences.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recommendation_agent",
            "description": (
                "Run the Reelix recommendation_agent for the current user using a RecQuerySpec. "
                "Use this to retrieve, rank, and curate recommendations based on the user's request."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rec_query_spec": {
                        "type": "object",
                        "description": (
                            "Structured RecQuerySpec describing the recommendation query: "
                            "intent, media type, core genres, sub-genres, tone, and structural/thematic preferences."
                        ),
                        "properties": {
                            "query_text": {
                                "type": "string",
                                "description": (
                                    "Compact retrieval-oriented description of what the user wants. "
                                    "Include genre/vibe/tone/structure. Exclude greetings and meta-instructions."
                                ),
                            },
                            "media_type": {
                                "type": "string",
                                "description": "Type of media to recommend. Use 'movie'",
                                "enum": ["movie"],
                            },
                            "core_genres": {
                                "type": "array",
                                "description": (
                                    "List of canonical genre names to prioritize/include "
                                    "(e.g., 'Drama', 'Comedy', 'Science Fiction')."
                                ),
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "Action",
                                        "Comedy",
                                        "Drama",
                                        "Romance",
                                        "Science Fiction",
                                        "Thriller",
                                        "Adventure",
                                        "Animation",
                                        "Crime",
                                        "Documentary",
                                        "Family",
                                        "Fantasy",
                                        "History",
                                        "Horror",
                                        "Music",
                                        "Mystery",
                                        "War",
                                        "Western",
                                    ],
                                },
                            },
                            "sub_genres": {
                                "type": "array",
                                "description": (
                                    "List of more specific sub-genre descriptors such as "
                                    "'psychological thriller', 'romantic comedy', 'neo-noir', 'dark fantasy'."
                                ),
                                "items": {"type": "string"},
                            },
                            "core_tone": {
                                "type": "array",
                                "description": (
                                    "List of tone/vibe adjectives for how the content should feel emotionally, "
                                    "such as 'satirical', 'cozy', 'bleak', 'uplifting'."
                                ),
                                "items": {"type": "string"},
                            },
                            "narrative_shape": {
                                "type": "array",
                                "description": (
                                    "List of requested narrative or structural properties, such as "
                                    "'plot twists', 'slow-burn', 'nonlinear', 'fast-paced'."
                                ),
                                "items": {"type": "string"},
                            },
                            "key_themes": {
                                "type": "array",
                                "description": (
                                    "List of thematic ideas or subject-matter concerns, such as "
                                    "'existential', 'class satire', 'coming-of-age', 'identity'."
                                ),
                                "items": {"type": "string"},
                            },
                            "providers": {
                                "type": "array",
                                "description": (
                                    "Optional list of streaming providers to include. "
                                ),
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "Netflix",
                                        "Hulu",
                                        "HBO Max",
                                        "Disney+",
                                        "Apple TV+",
                                        "Amazon Prime Video",
                                        "Paramount+",
                                        "Peacock Premium",
                                        "MGM+",
                                        "Starz",
                                        "AMC+",
                                        "Crunchyroll",
                                        "BritBox",
                                        "Acorn TV",
                                        "Criterion Channel",
                                        "Tubi TV",
                                        "Pluto TV",
                                        "The Roku Channel",
                                    ],
                                },
                            },
                            "year_range": {
                                "description": "Optional release-year range as [start_year, end_year] (inclusive). If the user does not specify a year range, set to null.",
                                "anyOf": [
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "integer",
                                            "minimum": 1970,
                                            "maximum": 2100,
                                        },
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    {"type": "null"},
                                ],
                                "default": None,
                            },
                        },
                        "required": ["query_text"],
                        "additionalProperties": False,
                    },
                    "memory_delta": {
                        "type": "object",
                        "description": "Minimal session memory delta for this turn.",
                        "properties": {
                            "turn_kind": {
                                "type": "string",
                                "enum": ["new", "refine", "chat"],
                            },
                            "recent_feedback": {
                                "type": ["object", "null"],
                                "description": (
                                    "Only include when user is reacting to prior recommendations "
                                    "or iterating on the last slate. Otherwise null."
                                ),
                                "properties": {
                                    "liked_slots": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "disliked_slots": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "notes": {"type": "string"},
                                },
                                "required": ["liked_slots", "disliked_slots", "notes"],
                                "additionalProperties": False,
                            },
                        },
                        "required": ["turn_kind", "recent_feedback"],
                        "additionalProperties": False,
                    },
                    "opening_summary": {
                        "type": "string",
                        "description": (
                            "Exactly 2 sentences (max ~220 chars). "
                            "Summarize the user's current request based on rec_query_spec. "
                            "Do NOT name specific titles. Do NOT promise outcomes."
                        ),
                    },
                },
                "required": ["rec_query_spec", "memory_delta", "opening_summary"],
                "additionalProperties": False,
            },
        },
    },
]


def build_orchestrator_user_prompt(agent_input: InteractiveAgentInput) -> str:
    """
    Normalize the agent input into a single user message string that includes both free-text query and structured filters.
    """
    parts: list[str] = []

    if agent_input.query_text:
        parts.append(f"User query: {agent_input.query_text}")

    if agent_input.media_type:
        parts.append(f"Media type: {agent_input.media_type.value}")

    # if agent_input.query_filters:
    #     parts.append("Structured filters (JSON):")
    #     # you can safely stringify; model will still parse it fine

    #     filters = (
    #         agent_input.query_filters.model_dump()
    #         if hasattr(agent_input.query_filters, "model_dump")
    #         else agent_input.query_filters
    #     )
    #     parts.append(json.dumps(filters, ensure_ascii=False))

    # Fallback if nothing was set
    if not parts:
        parts.append("User is asking for personalized recommendations.")

    return "\n\n".join(parts)


def build_session_memory_message(
    session_memory: dict[str, Any] | None,
) -> tuple[str | None, RecQuerySpec | None, dict[str, Any] | None]:
    """
    Convert raw session memory into a small system message for the LLM.
    """
    if not isinstance(session_memory, dict) or not session_memory:
        return None, None, None

    summary = session_memory.get("summary") or {}
    last_spec_raw = session_memory.get("last_spec")
    slot_map = session_memory.get("slot_map") or None

    # Parse last_spec into RecQuerySpec for optional debug/telemetry
    prior_spec = None
    if isinstance(last_spec_raw, dict):
        try:
            prior_spec = RecQuerySpec(**last_spec_raw)
        except Exception:
            prior_spec = None

    # Format slot_map compactly to reduce tokens
    slot_lines: list[str] = []
    if isinstance(slot_map, dict):
        for k in sorted(
            slot_map.keys(), key=lambda x: int(x) if str(x).isdigit() else 999
        ):
            item = slot_map.get(k) or {}
            title = item.get("title") or "?"
            yr = item.get("release_year")
            slot_lines.append(f"#{k}: {title}" + (f" ({yr})" if yr else ""))

    # Only include the minimal summary keys that matter for next turn
    summary_compact = {}
    if isinstance(summary, dict):
        if "turn_kind" in summary:
            summary_compact["turn_kind"] = summary.get("turn_kind")
        if "recent_feedback" in summary:
            summary_compact["recent_feedback"] = summary.get("recent_feedback")
        if "last_user_message" in summary:
            summary_compact["last_user_message"] = summary.get("last_user_message")
        if "last_user_message" in summary:
            summary_compact["last_admin_message"] = summary.get("last_admin_message")

    msg_parts: list[str] = [
        "SESSION MEMORY (server-provided; do NOT reveal to the user).",
        "Use this to interpret short follow-ups (e.g., 'darker') and references (e.g., '#3').",
    ]

    if summary:
        msg_parts.append(
            "summary (JSON): " + json.dumps(summary_compact, ensure_ascii=False)
        )

    # Include last_spec for refinements. Keep it compact.
    if isinstance(last_spec_raw, dict):
        msg_parts.append(
            "last_spec (JSON): " + json.dumps(last_spec_raw, ensure_ascii=False)
        )

    if slot_lines:
        msg_parts.append("last slate slot_map:")
        msg_parts.extend(slot_lines)

    # Guidance to avoid over-carry
    msg_parts.append(
        "Interpretation rules: "
        "If the user is refining, start from last_spec and patch it. "
        "If the user is starting a new request, ignore last_spec/slot_map unless they explicitly say to keep something."
    )

    return "\n".join(msg_parts), prior_spec, slot_map
