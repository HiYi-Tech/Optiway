from app.providers.local import optimize_local
from app.schemas import OptimizeRequest, Place
from app.tsp import haversine_m


def place(name: str, lat: float, lng: float) -> Place:
    return Place(name=name, lat=lat, lng=lng)


def test_haversine_is_close_to_known_distance() -> None:
    beijing = place("天安门", 39.9087, 116.3975)
    shanghai = place("外滩", 31.2400, 121.4900)
    distance = haversine_m(beijing, shanghai)
    assert 1_050_000 < distance < 1_080_000


def test_local_optimizer_reorders_intermediates() -> None:
    origin = place("起点", 0.0, 0.0)
    destination = place("终点", 0.0, 0.30)
    # Input order is deliberately not the shortest path.
    intermediates = [
        place("远点", 0.0, 0.25),
        place("近点", 0.0, 0.05),
        place("中点", 0.0, 0.15),
    ]

    response = optimize_local(
        OptimizeRequest(
            origin=origin,
            end_mode="fixed",
            destination=destination,
            intermediates=intermediates,
        ),
        "local",
    )

    assert response.provider == "local"
    assert response.end_mode == "fixed"
    assert response.optimized is True
    assert response.optimized_indices == [1, 2, 0]
    assert [stop.name for stop in response.stops] == ["起点", "近点", "中点", "远点", "终点"]


def test_local_optimizer_keeps_input_order_when_disabled() -> None:
    origin = place("起点", 0.0, 0.0)
    destination = place("终点", 0.0, 0.30)
    intermediates = [
        place("远点", 0.0, 0.25),
        place("近点", 0.0, 0.05),
    ]

    response = optimize_local(
        OptimizeRequest(
            origin=origin,
            end_mode="fixed",
            destination=destination,
            intermediates=intermediates,
            optimize=False,
        ),
        "local",
    )

    assert response.optimized is False
    assert response.optimized_indices == [0, 1]
    assert [stop.name for stop in response.stops] == ["起点", "远点", "近点", "终点"]


def test_local_open_route_orders_all_points_and_chooses_final_stop() -> None:
    origin = place("起点", 0.0, 0.0)
    points = [
        place("远点", 0.0, 0.25),
        place("近点", 0.0, 0.05),
        place("中点", 0.0, 0.15),
    ]

    response = optimize_local(
        OptimizeRequest(
            origin=origin,
            end_mode="open",
            intermediates=points,
        ),
        "local",
    )

    assert response.provider == "local"
    assert response.end_mode == "open"
    assert response.optimized is True
    assert response.optimized_indices == [1, 2, 0]
    assert [stop.name for stop in response.stops] == ["起点", "近点", "中点", "远点"]
    assert response.stops[0].role == "origin"
    assert response.stops[-1].role == "destination"
