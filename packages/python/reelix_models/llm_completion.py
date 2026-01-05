from __future__ import annotations

import time
from typing import Any

from openai import OpenAI
from reelix_core.config import CHAT_COMPLETION_MODEL


class OpenAIChatLLM:
    def __init__(
        self, client: OpenAI, *, request_timeout: float = 60.0, max_retries: int = 2
    ):
        self.client = client
        self.request_timeout = request_timeout
        self.max_retries = max_retries

    def stream(
        self,
        messages: list,
        model: str | None = None,
        **params: Any,
    ):
        call_params = params or {"temperature": 0.7, "top_p": 1.0}
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model or CHAT_COMPLETION_MODEL,
                    messages=messages,
                    stream=True,
                    **call_params,
                )

                for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
                return
            except Exception:
                if attempt >= self.max_retries:
                    raise
                time.sleep(0.5 * (2**attempt))