import math

from app.schemas import Place

EARTH_RADIUS_M = 6_371_000.0


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


def _held_karp_order(
    origin: Place,
    points: list[Place],
    destination: Place | None,
) -> list[int]:
    """Exact shortest path order over `points`.

    If `destination` is None, the path is open: it starts at `origin`, visits
    every point, and may end at whichever point is cheapest. Otherwise the
    path ends at the fixed destination.
    """
    count = len(points)
    if count <= 1:
        return list(range(count))

    size = 1 << count
    infinity = float("inf")
    # dp[mask][last] = shortest distance from origin, visiting mask, ending at last.
    dp = [[infinity] * count for _ in range(size)]
    parent = [[-1] * count for _ in range(size)]

    for index in range(count):
        dp[1 << index][index] = haversine_m(origin, points[index])

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
                candidate = current + haversine_m(points[last], points[nxt])
                next_mask = mask | bit
                if candidate < dp[next_mask][nxt]:
                    dp[next_mask][nxt] = candidate
                    parent[next_mask][nxt] = last
                remaining ^= bit

    full_mask = size - 1
    if destination is None:
        best_end = min(range(count), key=lambda index: dp[full_mask][index])
    else:
        best_end = min(
            range(count),
            key=lambda index: dp[full_mask][index] + haversine_m(points[index], destination),
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


def optimal_fixed_order(
    origin: Place,
    destination: Place,
    intermediates: list[Place],
) -> list[int]:
    """Optimal order of intermediates with both endpoints fixed."""
    return _held_karp_order(origin, intermediates, destination)


def optimal_open_order(origin: Place, points: list[Place]) -> list[int]:
    """Optimal open-path order starting at origin and ending anywhere."""
    return _held_karp_order(origin, points, None)
