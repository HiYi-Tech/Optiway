from typing import Any

import httpx

from app.config import ProviderName, settings
from app.providers.base import (
    ProviderNotConfiguredError,
    ProviderRequestError,
    RouteProviderError,
)
from app.schemas import OptimizeRequest, OptimizeResponse, Place, StopResult, StopRole
from app.tsp import optimal_open_order

GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = ",".join(
    [
        "routes.duration",
        "routes.distanceMeters",
        "routes.polyline.encodedPolyline",
        "routes.optimizedIntermediateWaypointIndex",
        "routes.legs.distanceMeters",
        "routes.legs.duration",
    ]
)
MODE_LABELS = {
    "DRIVE": "实时路况",
    "WALK": "步行",
    "BICYCLE": "骑行",
}


def decode_polyline(encoded: str) -> list[list[float]]:
    """Decode a Google encoded polyline into [longitude, latitude] pairs."""
    coordinates: list[list[float]] = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        shift = 0
        result = 0
        while True:
            if index >= len(encoded):
                return coordinates
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else result >> 1
        lat += delta_lat

        shift = 0
        result = 0
        while True:
            if index >= len(encoded):
                return coordinates
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lng = ~(result >> 1) if result & 1 else result >> 1
        lng += delta_lng
        coordinates.append([lng / 1e5, lat / 1e5])
    return coordinates


def _seconds(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("s"):
            text = text[:-1]
        try:
            return float(text)
        except ValueError:
            return 0.0
    return 0.0


def _role_for(index: int, total: int) -> StopRole:
    if index == 0:
        return "origin"
    if index == total - 1:
        return "destination"
    return "intermediate"


def _lat_lng(place: Place) -> dict[str, Any]:
    return {
        "location": {
            "latLng": {
                "latitude": place.lat,
                "longitude": place.lng,
            }
        }
    }


def _open_terminal_index(request: OptimizeRequest) -> int:
    """Pick the final stop for an open route.

    Google Routes requires a fixed destination. For open routes we use the
    local exact open-path solver to choose which point should be last, then let
    Google optimize the order of the remaining points.
    """
    pool = request.intermediates
    if not pool:
        raise ProviderRequestError("开放路线模式至少需要一个拜访点。")
    if request.optimize and len(pool) > 1:
        return optimal_open_order(request.origin, pool)[-1]
    return len(pool) - 1


def _parse_response(
    payload: dict[str, Any],
    request: OptimizeRequest,
    requested_provider: ProviderName,
    fallback_reason: str | None,
    *,
    destination: Place,
    google_intermediates: list[Place],
    intermediate_indices: list[int],
    terminal_index: int | None,
) -> OptimizeResponse:
    routes = payload.get("routes") or []
    if not routes:
        raise RouteProviderError("Google Routes 没有返回可用路线，请调整地点、出行方式或稍后重试。")

    route = routes[0]
    intermediate_count = len(google_intermediates)
    if request.optimize and intermediate_count > 0:
        raw_order = route.get("optimizedIntermediateWaypointIndex")
        if not isinstance(raw_order, list):
            raw_order = list(range(intermediate_count))
        order = [int(index) for index in raw_order]
        if sorted(order) != list(range(intermediate_count)):
            raise RouteProviderError("Google Routes 返回的途经点顺序不符合预期，请重试。")
    else:
        order = list(range(intermediate_count))

    if request.end_mode == "open":
        if terminal_index is None:
            raise RouteProviderError("开放路线缺少算法选择的最后一站。")
        ordered_pool_indices = [intermediate_indices[index] for index in order] + [terminal_index]
        ordered_points = [request.origin] + [
            request.intermediates[index] for index in ordered_pool_indices
        ]
        optimized_indices = ordered_pool_indices
        optimized = bool(request.optimize and len(request.intermediates) > 1)
    else:
        ordered_points = (
            [request.origin] + [google_intermediates[index] for index in order] + [destination]
        )
        optimized_indices = order
        optimized = bool(request.optimize and intermediate_count > 0)

    legs: list[Any] = route.get("legs") or []

    stops: list[StopResult] = []
    total_distance = 0.0
    total_duration = 0.0
    cumulative_duration = 0.0

    for index, place in enumerate(ordered_points):
        leg_distance = 0.0
        leg_duration = 0.0
        if index > 0 and index - 1 < len(legs):
            leg = legs[index - 1]
            leg_distance = float(leg.get("distanceMeters", 0.0))
            leg_duration = _seconds(leg.get("duration"))
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

    encoded_polyline = route.get("polyline", {}).get("encodedPolyline") or ""
    geometry = decode_polyline(encoded_polyline)
    if not geometry:
        geometry = [[point.lng, point.lat] for point in ordered_points]

    route_distance = route.get("distanceMeters")
    route_duration = route.get("duration")
    total_distance = float(route_distance) if route_distance is not None else total_distance
    total_duration = _seconds(route_duration) if route_duration is not None else total_duration

    mode_label = MODE_LABELS[request.travel_mode]
    if request.end_mode == "open":
        note = (
            f"Google Routes 开放路线（{mode_label}）：系统先选择最后一站，"
            "再由 Google 优化其余点位顺序。"
            if optimized
            else f"Google Routes 开放路线（{mode_label}）：保持输入顺序，"
            "最后一站为输入中的最后一个点位。"
        )
    elif optimized:
        note = f"由 Google Routes API 计算（{mode_label}），途经顺序由 optimizeWaypointOrder 优化。"
    else:
        note = f"由 Google Routes API 计算（{mode_label}），保持输入顺序。"

    return OptimizeResponse(
        provider="google",
        provider_label=f"Google Routes · {mode_label}",
        requested_provider=requested_provider,
        end_mode=request.end_mode,
        optimized=optimized,
        fallback_reason=fallback_reason,
        note=note,
        stops=stops,
        total_distance_meters=round(total_distance, 1),
        total_duration_seconds=round(total_duration, 1),
        geometry=geometry,
        optimized_indices=optimized_indices,
    )


async def optimize_google(
    request: OptimizeRequest,
    requested_provider: ProviderName,
    *,
    fallback_reason: str | None = None,
) -> OptimizeResponse:
    api_key = (settings.GOOGLE_MAPS_API_KEY or "").strip()
    if not api_key:
        raise ProviderNotConfiguredError("未配置 GOOGLE_MAPS_API_KEY，无法使用 Google Routes API。")

    if request.end_mode == "open":
        terminal_index = _open_terminal_index(request)
        destination = request.intermediates[terminal_index]
        intermediate_indices = [
            index for index in range(len(request.intermediates)) if index != terminal_index
        ]
        google_intermediates = [request.intermediates[index] for index in intermediate_indices]
    else:
        if request.destination is None:
            raise ProviderRequestError("固定终点模式需要提供终点。")
        destination = request.destination
        terminal_index = None
        intermediate_indices = list(range(len(request.intermediates)))
        google_intermediates = list(request.intermediates)

    body: dict[str, Any] = {
        "origin": _lat_lng(request.origin),
        "destination": _lat_lng(destination),
        "travelMode": request.travel_mode,
        "languageCode": "zh-CN",
        "units": "METRIC",
        "optimizeWaypointOrder": bool(request.optimize and google_intermediates),
    }
    if google_intermediates:
        body["intermediates"] = [_lat_lng(place) for place in google_intermediates]
    if request.travel_mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_AWARE"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
        "X-Server-Timeout": "20",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(GOOGLE_ROUTES_URL, json=body, headers=headers)
    except httpx.TimeoutException as exc:
        raise RouteProviderError("Google Routes API 请求超时，请稍后重试。") from exc
    except httpx.HTTPError as exc:
        raise RouteProviderError("无法连接 Google Routes API，请检查网络后重试。") from exc

    if response.status_code != 200:
        try:
            error_payload = response.json()
            error = error_payload.get("error", {}) if isinstance(error_payload, dict) else {}
            message = error.get("message") or response.text[:300]
        except ValueError:
            message = response.text[:300]
        raise RouteProviderError(
            f"Google Routes API 错误（HTTP {response.status_code}）：{message}"
        )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise RouteProviderError("Google Routes API 返回了无法解析的响应。") from exc

    return _parse_response(
        payload,
        request,
        requested_provider,
        fallback_reason,
        destination=destination,
        google_intermediates=google_intermediates,
        intermediate_indices=intermediate_indices,
        terminal_index=terminal_index,
    )
