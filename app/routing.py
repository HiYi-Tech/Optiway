from app.config import settings
from app.providers.base import RouteProviderError
from app.providers.google import optimize_google
from app.providers.local import optimize_local
from app.providers.osrm import optimize_osrm
from app.schemas import OptimizeRequest, OptimizeResponse


async def optimize_route(request: OptimizeRequest) -> OptimizeResponse:
    """Resolve the requested provider and fall back safely in auto mode."""
    requested = request.provider or settings.ROUTE_PROVIDER

    if requested == "local":
        return optimize_local(request, requested)

    if requested == "google":
        return await optimize_google(request, requested)

    if requested == "osrm":
        return await optimize_osrm(request, requested)

    # auto: Google when configured, then the free OSRM demo server, then offline.
    errors: list[str] = []
    if settings.google_enabled:
        try:
            return await optimize_google(request, requested)
        except RouteProviderError as exc:
            errors.append(f"Google：{exc}")

    try:
        return await optimize_osrm(request, requested)
    except RouteProviderError as exc:
        errors.append(f"OSRM：{exc}")

    reason = "；".join(errors)
    return optimize_local(
        request,
        requested,
        fallback_reason=reason or None,
        note="自动模式已降级到本地模拟，按直线距离和平均速度估算。",
    )
