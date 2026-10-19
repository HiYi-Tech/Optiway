import math

from app.config import ProviderName
from app.schemas import OptimizeRequest, OptimizeResponse, Place, StopResult, StopRole

EARTH_RADIUS_M = 6_371_000.0
AVERAGE_SPEED_KMH = {
    "DRIVE": 32.0,
    "WALK": 4.8,
    "BICYCLE": 15.0,
}


def haversine_m(a: Place, b: Place) -> float:
    """Great-circle distance between two places, in meters."""
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    delta_lat = lat2 - lat1
    delta_lng = math.radians(b.lng - a.lng)
    h = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def optimal_intermediate_order(
    origin: Place, destination: Place, intermediates: list[Place]
) -> list[int]:
    """Exact shortest path order for intermediate stops (Held-Karp).

    The demo caps intermediates at 10, so the 2^n * n^2 dynamic program is cheap.
    """
    count = len(intermediates)
    if count <= 1:
        return list(range(count))

    size = 1 << count
    infinity = float("inf")
    # dp[mask][last] = shortest distance from origin, visiting mask, ending at last.
    dp = [[infinity] * count for _ in range(size)]
    parent = [[-1] * count for _ in range(size)]

    for index in range(count):
        dp[1 << index][index] = haversine_m(origin, intermediates[index])

    for mask in range(size):
        for last in range(count):
            if not mask & (1 << last):
                continue
            current = dp[mask][last]
            if current == infinity:
                continue
            remaining = (size - 1) ^ mask
            while remaining:
                bit = remaining & -remaining
                nxt = bit.bit_length() - 1
                candidate = current + haversine_m(intermediates[last], intermediates[nxt])
                next_mask = mask | bit
                if candidate < dp[next_mask][nxt]:
                    dp[next_mask][nxt] = candidate
                    parent[next_mask][nxt] = last
                remaining ^= bit

    full_mask = size - 1
    best_end = min(
        range(count),
        key=lambda index: dp[full_mask][index] + haversine_m(intermediates[index], destination),
    )

    order: list[int] = []
    mask = full_mask
    end = best_end
    while end != -1:
        order.append(end)
        previous = parent[mask][end]
        mask ^= 1 << end
        end = previous
    order.reverse()
    return order


def optimize_local(
    request: OptimizeRequest,
    requested_provider: ProviderName,
    *,
    fallback_reason: str | None = None,
    note: str | None = None,
) -> OptimizeResponse:
    """Offline fallback: straight-line distances plus a simple average speed."""
    order = list(range(len(request.intermediates)))
    if request.optimize and len(request.intermediates) > 1:
        order = optimal_intermediate_order(
            request.origin, request.destination, request.intermediates
        )

    ordered_places = (
        [request.origin] + [request.intermediates[index] for index in order] + [request.destination]
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
        optimized=request.optimize and len(request.intermediates) > 0,
        fallback_reason=fallback_reason,
        note=note or "本地模拟按直线距离和平均速度估算，仅用于验证排序逻辑。",
        stops=stops,
        total_distance_meters=round(total_distance, 1),
        total_duration_seconds=round(total_duration, 1),
        geometry=geometry,
        optimized_indices=order,
    )
