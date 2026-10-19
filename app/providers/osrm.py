from typing import Any

import httpx

from app.config import ProviderName, settings
from app.providers.base import ProviderRequestError, RouteProviderError
from app.schemas import OptimizeRequest, OptimizeResponse, Place, StopResult, StopRole

PROVIDER_LABEL = "OSRM · 真实道路"


def _coordinate_string(points: list[Place]) -> str:
    return ";".join(f"{point.lng:.6f},{point.lat:.6f}" for point in points)


def _role_for(index: int, total: int) -> StopRole:
    if index == 0:
        return "origin"
    if index == total - 1:
        return "destination"
    return "intermediate"


def _parse_payload(
    payload: dict[str, Any],
    request: OptimizeRequest,
    use_trip: bool,
    requested_provider: ProviderName,
    fallback_reason: str | None,
) -> OptimizeResponse:
    points = [request.origin, *request.intermediates, request.destination]

    if use_trip:
        trips = payload.get("trips") or []
        waypoints = payload.get("waypoints") or []
        if not trips:
            raise RouteProviderError("OSRM 没有返回可用路线，请调整地点后重试。")
        if len(waypoints) != len(points):
            raise RouteProviderError("OSRM 返回的途经点数量不匹配，请重试。")
        route = trips[0]
        try:
            order = sorted(
                range(len(points)),
                key=lambda index: waypoints[index]["waypoint_index"],
            )
        except (KeyError, TypeError) as exc:
            raise RouteProviderError("OSRM 返回的途经点顺序无法解析，请重试。") from exc
        if order[0] != 0 or order[-1] != len(points) - 1:
            raise RouteProviderError("OSRM 返回的起终点顺序不符合预期，请重试。")
        optimized_indices = [index - 1 for index in order if 0 < index < len(points) - 1]
    else:
        routes = payload.get("routes") or []
        if not routes:
            raise RouteProviderError("OSRM 没有返回可用路线，请调整地点后重试。")
        route = routes[0]
        order = list(range(len(points)))
        optimized_indices = list(range(len(request.intermediates)))

    ordered_points = [points[index] for index in order]
    legs: list[Any] = route.get("legs") or []
    geometry: list[list[float]] = route.get("geometry", {}).get("coordinates") or []

    stops: list[StopResult] = []
    total_distance = 0.0
    total_duration = 0.0
    cumulative_duration = 0.0

    for index, place in enumerate(ordered_points):
        leg_distance = 0.0
        leg_duration = 0.0
        if index > 0 and index - 1 < len(legs):
            leg = legs[index - 1]
            leg_distance = float(leg.get("distance", 0.0))
            leg_duration = float(leg.get("duration", 0.0))
            total_distance += leg_distance
            total_duration += leg_duration
            cumulative_duration += leg_duration

        stops.append(
            StopResult(
                name=place.name,
                lat=place.lat,
                lng=place.lng,
                role=_role_for(index, len(ordered_points)),
                leg_distance_meters=round(leg_distance, 1),
                leg_duration_seconds=round(leg_duration, 1),
                cumulative_duration_seconds=round(cumulative_duration, 1),
            )
        )

    if not geometry:
        geometry = [[point.lng, point.lat] for point in ordered_points]

    optimized = bool(request.optimize and len(request.intermediates) > 0)
    note = (
        "由 OSRM 公共演示服务计算，按预计行驶时间优化途经顺序；公共实例不保证 SLA。"
        if optimized
        else "由 OSRM 公共演示服务计算，保持输入顺序；公共实例不保证 SLA。"
    )

    return OptimizeResponse(
        provider="osrm",
        provider_label=PROVIDER_LABEL,
        requested_provider=requested_provider,
        optimized=optimized,
        fallback_reason=fallback_reason,
        note=note,
        stops=stops,
        total_distance_meters=round(total_distance, 1),
        total_duration_seconds=round(total_duration, 1),
        geometry=geometry,
        optimized_indices=optimized_indices,
    )


async def optimize_osrm(
    request: OptimizeRequest,
    requested_provider: ProviderName,
    *,
    fallback_reason: str | None = None,
) -> OptimizeResponse:
    """Call the public OSRM demo server. It only exposes the driving profile."""
    if request.travel_mode != "DRIVE":
        raise ProviderRequestError(
            "OSRM 公共演示服务仅提供驾车路线；步行/骑行请配置 Google API Key 或选择本地模拟。"
        )

    points = [request.origin, *request.intermediates, request.destination]
    use_trip = request.optimize and len(request.intermediates) > 0
    service = "trip" if use_trip else "route"
    base_url = settings.OSRM_BASE_URL.rstrip("/")
    url = f"{base_url}/{service}/v1/driving/{_coordinate_string(points)}"

    params: dict[str, str] = {
        "geometries": "geojson",
        "overview": "simplified",
        "steps": "false",
    }
    if use_trip:
        params.update(
            {
                "roundtrip": "false",
                "source": "first",
                "destination": "last",
            }
        )

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": "optiway-demo/0.1"},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
    except httpx.TimeoutException as exc:
        raise RouteProviderError("OSRM 请求超时，请稍后重试或切换到本地模拟。") from exc
    except httpx.HTTPStatusError as exc:
        raise RouteProviderError(
            f"OSRM 返回 HTTP {exc.response.status_code}，请稍后重试或切换到本地模拟。"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise RouteProviderError("无法连接 OSRM 服务，请稍后重试或切换到本地模拟。") from exc

    if payload.get("code") != "Ok":
        message = payload.get("message") or payload.get("code") or "未知错误"
        raise RouteProviderError(f"OSRM 无法规划路线：{message}")

    return _parse_payload(payload, request, use_trip, requested_provider, fallback_reason)
