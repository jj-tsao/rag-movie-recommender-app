from functools import lru_cache

from reelix_core.llm_client import LlmClient


@lru_cache(maxsize=1)
def _get_llm_client_singleton() -> LlmClient:
    return LlmClient()


def get_chat_completion_llm() -> LlmClient:
    """
    FastAPI dependency that returns a shared LlmClient instance.
    """
    return _get_llm_client_singleton()
