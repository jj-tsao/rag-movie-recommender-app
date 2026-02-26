"""
Unified LLM client — async (chat / chat_stream) and sync (stream) wrappers
around the OpenAI Chat Completions API.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator
from typing import Any, Optional

from openai import AsyncOpenAI, OpenAI


class LlmClient:
    """
    Thin wrapper around OpenAI's chat completion API.

    Async methods (chat, chat_stream) use AsyncOpenAI.
    Sync method (stream) uses OpenAI — lazily initialised on first call.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        timeout: float | None = 20.0,
        api_key: str | None = None,
        max_retries: int = 2,
    ) -> None:
        client_kwargs: dict = {"timeout": timeout}
        if api_key is not None:
            client_kwargs["api_key"] = api_key

        self._async_client = AsyncOpenAI(**client_kwargs)
        self._default_model = model
        self._max_retries = max_retries

        # Lazy-init: only created when stream() is called
        self._sync_client: OpenAI | None = None
        self._sync_client_kwargs = client_kwargs

    def _get_sync_client(self) -> OpenAI:
        if self._sync_client is None:
            self._sync_client = OpenAI(**self._sync_client_kwargs)
        return self._sync_client

    # ── Async: non-streaming ──────────────────────────────────────────

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = "auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_args: Optional[dict[str, Any]] = None,
    ):
        """
        Call the OpenAI chat completion endpoint with optional tools.

        Returns the raw OpenAI response object.
        """
        kwargs: dict[str, Any] = dict(
            model=model or self._default_model,
            messages=messages,
            temperature=temperature,
        )

        if tools is not None:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if extra_args:
            kwargs.update(extra_args)

        resp = await self._async_client.chat.completions.create(**kwargs)
        return resp

    # ── Async: streaming ──────────────────────────────────────────────

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = "auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_args: Optional[dict[str, Any]] = None,
        include_usage: bool = False,
        top_p: float = 1.0,
    ) -> AsyncIterator[str]:
        """
        Stream content deltas from the OpenAI chat completion endpoint.

        Yields strings (content deltas) suitable for SSE streaming.
        """
        kwargs: dict[str, Any] = dict(
            model=model or self._default_model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            stream=True,
        )

        if include_usage:
            kwargs["stream_options"] = {"include_usage": True}

        if tools is not None:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if extra_args:
            kwargs.update(extra_args)

        stream = await self._async_client.chat.completions.create(**kwargs)

        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue

            delta = getattr(choices[0], "delta", None)
            if not delta:
                continue

            content = getattr(delta, "content", None)
            if content:
                yield content

    # ── Sync: streaming (with retry) ──────────────────────────────────

    def stream(
        self,
        messages: list,
        model: str | None = None,
        **params: Any,
    ) -> Iterator[str]:
        """
        Synchronous streaming generator with retry logic.

        Yields content delta strings. Retries up to max_retries on failure.
        """
        call_params = params or {"temperature": 0.7, "top_p": 1.0}
        client = self._get_sync_client()

        for attempt in range(self._max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model or self._default_model,
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
                if attempt >= self._max_retries:
                    raise
                time.sleep(0.5 * (2**attempt))
