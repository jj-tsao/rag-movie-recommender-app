import os
import time
import httpx
from contextlib import asynccontextmanager

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from postgrest.exceptions import APIError as PgRestError
from reelix_core.errors import DomainError
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient

from reelix_core.config import (
    NLTK_PATH,
    QDRANT_MOVIE_COLLECTION_NAME,
    QDRANT_TV_COLLECTION_NAME,
)

os.environ.setdefault("NLTK_DATA", str(NLTK_PATH))
from reelix_logging.rec_logger import TelemetryLogger
from app.infrastructure.cache.redis_infra import make_redis_clients
from app.infrastructure.cache.ticket_store import TicketStore
from app.infrastructure.cache.state_store import StateStore
from app.infrastructure.cache.why_cache import WhyCache
from .routers import all_routers


class Settings(BaseSettings):
    app_name: str = "Reelix Discovery Agent API"

    # credentials
    qdrant_endpoint: str | None = None
    qdrant_api_key: str | None = None
    supabase_url: str | None = None
    supabase_api_key: str | None = None
    openai_api_key: str | None = None
    redis_url: str | None = None

    # ticket_store config
    ticket_namespace: str = "reelix:ticket:"
    why_cache_namespace: str = "reelix:why:"
    session_namespace: str = "reelix:agent:session:"
    ticket_ttl_sec: int = 3600  # 60 min cap
    session_ttl_sec: int = 7 * 24 * 3600  # 7d cap
    why_cache_ttl_sec: int = 14 * 24 * 3600  # 2 weeks cap

    # env config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def _should_init_recommendation() -> bool:
    flag = os.getenv("REELIX_SKIP_RECOMMENDER_INIT", "")
    return flag.strip().lower() not in {"1", "true", "yes"}


def _init_recommendation_stack(app: FastAPI) -> None:

    from reelix_models.custom_models import (
        load_bm25_files,
        load_sentence_model,
    )
    from reelix_retrieval.base_retriever import BaseRetriever
    from reelix_recommendation.recommend import RecommendPipeline
    from reelix_retrieval.query_encoder import Encoder
    from reelix_agent.orchestrator.agent_rec_runner import AgentRecRunner
    from reelix_recommendation.recipes import InteractiveRecipe, ForYouFeedRecipe
    from reelix_agent.tools import build_registry, ToolRunner

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    startup_t0 = time.perf_counter()

    # == Verify required credits ==
    required = {
        "QDRANT_ENDPOINT": app.state.settings.qdrant_endpoint,
        "QDRANT_API_KEY": app.state.settings.qdrant_api_key,
        "SUPABASE_URL": app.state.settings.supabase_url,
        "SUPABASE_API_KEY": app.state.settings.supabase_api_key,
        "OPENAI_API_KEY": app.state.settings.openai_api_key,
        "REDIS_URL": app.state.settings.redis_url,
    }
    missing = [
        name for name, value in required.items() if not (value and value.strip())
    ]
    if missing:
        raise RuntimeError(
            "Missing credentials in environment: " + ", ".join(sorted(missing))
        )

    # == Initialize recommendation stacks ==
    embed_model = load_sentence_model()
    bm25_models, bm25_vocabs = load_bm25_files()
    query_encoder = Encoder(embed_model, bm25_models, bm25_vocabs)
    app.state.qdrant = QdrantClient(
        url=app.state.settings.qdrant_endpoint,
        api_key=app.state.settings.qdrant_api_key,
    )

    base_retriever = BaseRetriever(
        app.state.qdrant,
        movie_collection=QDRANT_MOVIE_COLLECTION_NAME,
        tv_collection=QDRANT_TV_COLLECTION_NAME,
        dense_vector_name="dense_vector",
        sparse_vector_name="sparse_vector",
    )
    pipeline = RecommendPipeline(base_retriever, rrf_k=60)

    app.state.query_encoder = query_encoder
    app.state.recommend_pipeline = pipeline
    app.state.agent_rec_runner = AgentRecRunner(
        pipeline=pipeline,
        query_encoder=query_encoder,
    )
    app.state.recipes = {
        "for_you_feed": ForYouFeedRecipe(query_encoder=app.state.query_encoder),
        "interactive": InteractiveRecipe(query_encoder=app.state.query_encoder),
    }
    # == Initialize agent Tool Infrastructure ==

    app.state.tool_registry = build_registry()
    app.state.tool_runner = ToolRunner(app.state.tool_registry)

    # == Initialize Redis stores ==
    redis_clients = make_redis_clients(app.state.settings.redis_url)

    app.state.ticket_store = TicketStore(
        client=redis_clients.bytes,
        namespace=app.state.settings.ticket_namespace,
        absolute_ttl_sec=app.state.settings.ticket_ttl_sec,
    )

    app.state.state_store = StateStore(
        client=redis_clients.bytes,
        namespace=app.state.settings.session_namespace,
        absolute_ttl_sec=app.state.settings.session_ttl_sec,
    )

    app.state.why_cache = WhyCache(
        client=redis_clients.text,
        namespace=app.state.settings.why_cache_namespace,
        absolute_ttl_sec=app.state.settings.why_cache_ttl_sec,
    )

    print(f"🔧 Total startup time: {time.perf_counter() - startup_t0:.2f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(find_dotenv(), override=False)

    settings = Settings()
    app.state.settings = settings

    supabase_url = app.state.settings.supabase_url
    supabase_api_key = app.state.settings.supabase_api_key

    if not supabase_url or not supabase_api_key:
        raise RuntimeError("Missing Supabase credits")

    http_client = httpx.AsyncClient(timeout=5.0)

    logger = TelemetryLogger(
        supabase_url,
        supabase_api_key,
        client=http_client,
        timeout_s=5.0,
    )

    app.state.logger = logger

    # Eager init of external clients/models
    if _should_init_recommendation():
        try:
            _init_recommendation_stack(app)
        except ModuleNotFoundError as exc:
            missing = exc.name or "dependency"
            raise RuntimeError(
                f"Missing dependency '{missing}' required for recommendation bootstrap. "
                "Install it or set REELIX_SKIP_RECOMMENDER_INIT=1 to skip initialization."
            ) from exc
    else:
        print(
            "⚠️ Recommendation stack initialization skipped by REELIX_SKIP_RECOMMENDER_INIT"
        )

    try:
        yield
    finally:
        await http_client.aclose()
        await app.state.why_cache.aclose()


app = FastAPI(title="Reelix Discovery Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://reelixai.netlify.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version="0.1.0",
        description="Reelix Discovery Agent API",
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            operation.setdefault("security", []).append({"BearerAuth": []})
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


@app.exception_handler(PgRestError)
async def postgrest_error_handler(request: Request, exc: PgRestError):
    # Fallback if any PgRestError leaks past the repo mapping
    status = 400 if getattr(exc, "code", "") in ("22P02", "23502") else 500
    return JSONResponse(
        status_code=status,
        content={"error": {"code": "db_error", "message": "database error"}},
    )


@app.get("/health")
def health():
    s = app.state.settings
    return {"status": "ok", "service": s.app_name}


@app.get("/")
def read_root():
    s = app.state.settings
    return {"status": "ok", "service": s.app_name}


for r in all_routers:
    app.include_router(r)
