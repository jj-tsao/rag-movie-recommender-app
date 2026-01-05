from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, cast

from fastapi import HTTPException, Request, status
from qdrant_client import QdrantClient
from reelix_agent.orchestrator.agent_rec_runner import AgentRecRunner

if TYPE_CHECKING:
    from reelix_logging.rec_logger import TelemetryLogger
    from reelix_models.llm_completion import OpenAIChatLLM
    from reelix_recommendation.recommend import RecommendPipeline
    from reelix_retrieval.query_encoder import Encoder
else:
    RecommendPipeline = Any  # type: ignore
    Encoder = Any  # type: ignore
    OpenAIChatLLM = Any  # type: ignore
    TelemetryLogger = Any  # type: ignore


def _get_state_attr(request: Request, name: str, error_detail: str) -> Any:
    value = getattr(request.app.state, name, None)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        )
    return value


def get_settings(request: Request) -> Any:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Settings not initialized",
        )
    return settings


def get_qdrant(request: Request) -> QdrantClient:
    return cast(
        QdrantClient,
        _get_state_attr(request, "qdrant", "QDRANT client not initialized"),
    )


def get_query_encoder(request: Request) -> Encoder:
    return cast(
        Encoder,
        _get_state_attr(request, "query_encoder", "Query Encoder not initialized"),
    )


def get_recommend_pipeline(request: Request) -> "RecommendPipeline":
    return cast(
        "RecommendPipeline",
        _get_state_attr(
            request,
            "recommend_pipeline",
            "Recommendation pipeline not initialized",
        ),
    )


def get_agent_rec_runner(request: Request) -> "AgentRecRunner":
    return cast(
        "AgentRecRunner",
        _get_state_attr(
            request,
            "agent_rec_runner",
            "agent recommendation runner not initialized",
        ),
    )


class RecipeRegistry:
    def __init__(self, data: dict):
        self._data = data

    def get(self, *, kind: str):
        try:
            return self._data[kind]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown recipe kind: {kind}")


def get_recipe_registry(request: Request) -> RecipeRegistry:
    return RecipeRegistry(request.app.state.recipes)


def get_chat_completion_llm(request: Request) -> OpenAIChatLLM:
    return cast(
        OpenAIChatLLM,
        _get_state_attr(
            request,
            "chat_completion_llm",
            "Chat completion llm not initialized",
        ),
    )


def get_interactive_stream_fn(request: Request) -> Callable:
    fn = getattr(request.app.state, "interactive_stream_fn", None)
    if not callable(fn):
        raise HTTPException(
            status_code=503, detail="Recommendation service is initializing."
        )
    return fn


@dataclass(frozen=True)
class SupabaseCreds:
    url: str
    api_key: str


def get_supabase_creds(request: Request) -> SupabaseCreds:
    settings = get_settings(request)
    return SupabaseCreds(
        url=settings.supabase_url,
        api_key=settings.supabase_api_key,
    )


def get_logger(request: Request) -> TelemetryLogger:
    return cast(
        TelemetryLogger,
        _get_state_attr(request, "logger", "Telemetry logger not initialized"),
    )
