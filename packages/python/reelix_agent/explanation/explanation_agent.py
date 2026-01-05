from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

import anyio


@dataclass
class WhyItem:
    media_id: str
    why: str


@dataclass
class WhyEvent:
    type: Literal["item", "heartbeat"]
    item: WhyItem | None = None


async def stream_why_events(
    *,
    chat_llm,
    messages: list[dict[str, Any]],
    model: str,
    params: dict[str, Any],
    heartbeat_sec: float = 15.0,
) -> AsyncIterator[WhyEvent]:
    """
    Streams LLM deltas, parses JSONL, yields WhyEvents:
      - WhyEvent(type="item", item=WhyItem(...))
      - WhyEvent(type="heartbeat")
    """
    buffer = ""
    stream = chat_llm.chat_stream(messages=messages, model=model, **params)
    it = stream.__aiter__()

    while True:
        try:
            with anyio.fail_after(heartbeat_sec):
                delta = await it.__anext__()
        except TimeoutError:
            # Let the API layer decide how to express a heartbeat (e.g., SSE comment frame)
            yield WhyEvent(type="heartbeat")
            continue
        except StopAsyncIteration:
            break

        buffer += delta

        # parse complete lines
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # incomplete JSON line, restore and wait for more
                buffer = line + "\n" + buffer
                break

            item = _coerce_why_item(obj)
            if item:
                yield WhyEvent(type="item", item=item)

    # flush tail if it’s a complete object
    tail = buffer.strip()
    if tail:
        try:
            obj = json.loads(tail)
            item = _coerce_why_item(obj)
            if item:
                yield WhyEvent(type="item", item=item)
        except Exception:
            pass


def _coerce_why_item(obj: dict[str, Any]) -> WhyItem | None:
    media_id = obj.get("media_id")
    why = obj.get("why")
    if not media_id or not isinstance(why, str):
        return None

    return WhyItem(
        media_id=str(media_id),
        why=why,
    )
