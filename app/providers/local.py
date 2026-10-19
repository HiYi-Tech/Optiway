from app.config import ProviderName
from app.providers.base import ProviderRequestError
from app.schemas import OptimizeRequest, OptimizeResponse, StopResult, StopRole
from app.tsp import haversine_m, optimal_fixed_order, optimal_open_order

AVERAGE_SPEED_KMH = {
    "DRIVE": 32.0,
    "WALK": 4.8,
    "BICYCLE": 15.0,
}


def optimize_local(
    request: OptimizeRequest,
    requested_provider: ProviderName,
    *,
    fallback_reason: str | None = None,
    note: str | None = None,
) -> OptimizeResponse:
    """Offline fallback: straight-line distances plus a simple average speed."""
    if request.end_mode == "open":
        pool = request.intermediates
        if not pool:
            raise ProviderRequestError("开放路线模式至少需要一个拜访点。")

        order = list(range(len(pool)))
        if request.optimize and len(pool) > 1:
            order = optimal_open_order(request.origin, pool)
        ordered_places = [request.origin] + [pool[index] for index in order]
        optimized = request.optimize and len(pool) > 1
        note_fallback = (
            "本地模拟：仅固定起点，其余点位顺序和最后一站由算法选择；按直线距离和平均速度估算。"
            if optimized
            else "本地模拟：仅固定起点，保持输入顺序；按直线距离和平均速度估算。"
        )
    else:
        destination = request.destination
        if destination is None:
            raise ProviderRequestError("固定终点模式需要提供终点。")

        order = list(range(len(request.intermediates)))
        if request.optimize and len(request.intermediates) > 1:
            order = optimal_fixed_order(request.origin, destination, request.intermediates)
        ordered_places = (
            [request.origin] + [request.intermediates[index] for index in order] + [destination]
        )
        optimized = request.optimize and len(request.intermediates) > 0
        note_fallback = (
            "本地模拟：起点和终点固定，中间点位按直线距离优化；耗时按平均速度估算。"
            if optimized
            else "本地模拟：保持输入顺序，耗时按平均速度估算。"
        )

    speed_mps = AVERAGE_SPEED_KMH[request.travel_mode] * 1000 / 3600
    stops: list[StopResult] = []
    geometry: list[list[float]] = [[ordered_places[0].lng, ordered_places[0].lat]]
    total_distance = 0.0
    total_duration = 0.0
    cumulative_duration = 0.0

    for index, place in enumerate(ordered_places):
        role: StopRole
        if index == 0:
            role = "origin"
        elif index == len(ordered_places) - 1:
            role = "destination"
        else:
            role = "intermediate"

        leg_distance = 0.0
        leg_duration = 0.0
        if index > 0:
            previous = ordered_places[index - 1]
            leg_distance = haversine_m(previous, place)
            leg_duration = leg_distance / speed_mps
            total_distance += leg_distance
            total_duration += leg_duration
            cumulative_duration += leg_duration
            geometry.append([place.lng, place.lat])

        stops.append(
            StopResult(
                name=place.name,
                lat=place.lat,
                lng=place.lng,
                role=role,
                leg_distance_meters=round(leg_distance, 1),
                leg_duration_seconds=round(leg_duration, 1),
                cumulative_duration_seconds=round(cumulative_duration, 1),
            )
        )

    return OptimizeResponse(
        provider="local",
        provider_label="本地模拟",
        requested_provider=requested_provider,
        end_mode=request.end_mode,
        optimized=optimized,
        fallback_reason=fallback_reason,
        note=note or note_fallback,
        stops=stops,
        total_distance_meters=round(total_distance, 1),
        total_duration_seconds=round(total_duration, 1),
        geometry=geometry,
        optimized_indices=order,
    )
