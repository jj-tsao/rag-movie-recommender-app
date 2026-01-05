from typing import Protocol, Mapping, Any

class EventEmitter(Protocol):
    async def emit(self, name: str, payload: Mapping[str, Any]) -> None: ...

class NoopEmitter:
    async def emit(self, name: str, payload):  # type: ignore[override]
        return None
