from reelix_core.types import UserSignals
from reelix_ranking.types import Candidate
from reelix_llm.client import LlmClient
from reelix_agent.core.types import RecQuerySpec

from .curator_prompts import CURATOR_PROMPT_S, build_curator_user_prompt


async def run_curator_agent(
    *,
    query_text: str,
    spec: RecQuerySpec,
    candidates: list[Candidate],
    llm_client: LlmClient,
    user_signals: UserSignals | None = None,
) -> str:
    system_msg = {
        "role": "system",
        "content": CURATOR_PROMPT_S,
    }

    user_prompt = build_curator_user_prompt(
        candidates=candidates,
        query_text=query_text,
        spec=spec,
        user_signals=user_signals,
    )

    user_msg = {"role": "user", "content": user_prompt}

    resp = await llm_client.chat(
        messages=[system_msg, user_msg],
        tools=None,
        tool_choice=None,
        temperature=0.1,
        model="gpt-4.1-mini",
    )

    content = resp.choices[0].message.content

    return content
