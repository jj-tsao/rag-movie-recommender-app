from .discovery import router as discovery_router
from .routes_interactions import router as interactions_router
from .routes_taste_profile import router as taste_profile_router
from .routes_user_settings import router as user_settings_router
from .routes_watchlist import router as watchlist_router

all_routers = [
    discovery_router,
    interactions_router,
    taste_profile_router,
    user_settings_router,
    watchlist_router,
]
