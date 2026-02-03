"""
Discovery routers module. Combines all discovery-related endpoints under the /discovery prefix.
"""

from fastapi import APIRouter

from .explore import router as explore_router
from .for_you import router as for_you_router
from .telemetry import router as telemetry_router

router = APIRouter(prefix="/discovery")

router.include_router(explore_router)
router.include_router(for_you_router)
router.include_router(telemetry_router)