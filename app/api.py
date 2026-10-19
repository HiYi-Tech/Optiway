from fastapi import APIRouter, HTTPException

from app import __version__
from app.config import settings
from app.places import CITIES
from app.providers.base import RouteProviderError
from app.routing import optimize_route
from app.schemas import (
    HealthResponse,
    OptimizeRequest,
    OptimizeResponse,
    PlacesResponse,
)

router = APIRouter(prefix="/api", tags=["route"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        version=__version__,
        google_configured=settings.google_enabled,
        default_provider=settings.ROUTE_PROVIDER,
        osrm_base_url=settings.OSRM_BASE_URL,
        max_intermediates=settings.MAX_INTERMEDIATES,
        map_tile_url=settings.MAP_TILE_URL,
        map_tile_attribution=settings.MAP_TILE_ATTRIBUTION,
        map_tile_max_zoom=settings.MAP_TILE_MAX_ZOOM,
    )


@router.get("/places", response_model=PlacesResponse)
async def places() -> PlacesResponse:
    return PlacesResponse(cities=CITIES)


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(payload: OptimizeRequest) -> OptimizeResponse:
    if len(payload.intermediates) > settings.MAX_INTERMEDIATES:
        point_label = "拜访点" if payload.end_mode == "open" else "途经点"
        raise HTTPException(
            status_code=422,
            detail=f"最多支持 {settings.MAX_INTERMEDIATES} 个{point_label}。",
        )
    try:
        return await optimize_route(payload)
    except RouteProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
