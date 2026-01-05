from .routes_discovery import router as discover_router
from .routes_agent import router as agent_router
from .routes_recommendations import router as recommend_router
from .routes_interactions import router as interactions_router
from .routes_taste_profile import router as taste_profile_router
from .routes_user_settings import router as user_settings_router
from .routes_watchlist import router as watchlist_router

all_routers = [
    discover_router,
    agent_router,
    recommend_router,
    interactions_router,
    taste_profile_router,
    user_settings_router,
    watchlist_router,
]
