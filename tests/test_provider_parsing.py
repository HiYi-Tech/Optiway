from app.config import ProviderName
from app.providers.google import _open_terminal_index
from app.providers.google import _parse_response as parse_google_response
from app.providers.osrm import _parse_payload as parse_osrm_payload
from app.schemas import OptimizeRequest, Place

A = Place(name="A", lat=39.90, lng=116.40)
B = Place(name="B", lat=39.91, lng=116.40)
C = Place(name="C", lat=39.93, lng=116.41)
D = Place(name="D", lat=39.94, lng=116.42)


def fixed_request(provider: ProviderName) -> OptimizeRequest:
    return OptimizeRequest(
        origin=A,
        end_mode="fixed",
        destination=D,
        intermediates=[B, C],
        provider=provider,
    )


def open_request(provider: ProviderName) -> OptimizeRequest:
    return OptimizeRequest(
        origin=A,
        end_mode="open",
        intermediates=[B, C, D],
        provider=provider,
    )


def test_google_open_terminal_uses_open_path_solver() -> None:
    request = OptimizeRequest(
        origin=Place(name="O", lat=0.0, lng=0.0),
        end_mode="open",
        intermediates=[
            Place(name="near", lat=0.0, lng=0.05),
            Place(name="far", lat=0.0, lng=0.25),
            Place(name="mid", lat=0.0, lng=0.15),
        ],
        provider="google",
    )

    assert _open_terminal_index(request) == 1


def test_google_response_uses_optimized_waypoint_order() -> None:
    payload = {
        "routes": [
            {
                "distanceMeters": 1234,
                "duration": "456s",
                "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC"},
                "optimizedIntermediateWaypointIndex": [1, 0],
                "legs": [
                    {"distanceMeters": 100, "duration": "10s"},
                    {"distanceMeters": 200, "duration": "20s"},
                    {"distanceMeters": 934, "duration": "426s"},
                ],
            }
        ]
    }
    request = fixed_request("google")

    response = parse_google_response(
        payload,
        request,
        "google",
        None,
        destination=D,
        google_intermediates=[B, C],
        intermediate_indices=[0, 1],
        terminal_index=None,
    )

    assert response.provider == "google"
    assert response.end_mode == "fixed"
    assert response.optimized is True
    assert response.optimized_indices == [1, 0]
    assert [stop.name for stop in response.stops] == ["A", "C", "B", "D"]
    assert response.total_distance_meters == 1234
    assert response.total_duration_seconds == 456
    assert response.stops[1].leg_distance_meters == 100
    assert response.geometry


def test_google_open_response_maps_terminal_back_to_pool() -> None:
    payload = {
        "routes": [
            {
                "distanceMeters": 1500,
                "duration": "500s",
                "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC"},
                "optimizedIntermediateWaypointIndex": [1, 0],
                "legs": [
                    {"distanceMeters": 100, "duration": "10s"},
                    {"distanceMeters": 200, "duration": "20s"},
                    {"distanceMeters": 1200, "duration": "470s"},
                ],
            }
        ]
    }
    request = open_request("google")

    response = parse_google_response(
        payload,
        request,
        "google",
        None,
        destination=D,
        google_intermediates=[B, C],
        intermediate_indices=[0, 1],
        terminal_index=2,
    )

    assert response.end_mode == "open"
    assert response.optimized is True
    assert response.optimized_indices == [1, 0, 2]
    assert [stop.name for stop in response.stops] == ["A", "C", "B", "D"]
    assert response.stops[-1].role == "destination"


def test_osrm_response_uses_waypoint_index_order() -> None:
    payload = {
        "code": "Ok",
        "waypoints": [
            {"waypoint_index": 0},
            {"waypoint_index": 2},
            {"waypoint_index": 1},
            {"waypoint_index": 3},
        ],
        "trips": [
            {
                "distance": 3000,
                "duration": 600,
                "geometry": {
                    "coordinates": [[116.40, 39.90], [116.41, 39.94]],
                },
                "legs": [
                    {"distance": 1000, "duration": 200},
                    {"distance": 1000, "duration": 200},
                    {"distance": 1000, "duration": 200},
                ],
            }
        ],
    }

    response = parse_osrm_payload(
        payload,
        fixed_request("osrm"),
        [A, B, C, D],
        use_trip=True,
        requested_provider="osrm",
        fallback_reason=None,
    )

    assert response.end_mode == "fixed"
    assert response.provider == "osrm"
    assert response.optimized is True
    assert response.optimized_indices == [1, 0]
    assert [stop.name for stop in response.stops] == ["A", "C", "B", "D"]
    assert response.total_distance_meters == 3000
    assert response.total_duration_seconds == 600
    assert response.stops[2].leg_distance_meters == 1000


def test_osrm_open_response_orders_all_points() -> None:
    payload = {
        "code": "Ok",
        "waypoints": [
            {"waypoint_index": 0},
            {"waypoint_index": 3},
            {"waypoint_index": 1},
            {"waypoint_index": 2},
        ],
        "trips": [
            {
                "distance": 3000,
                "duration": 600,
                "geometry": {
                    "coordinates": [[116.40, 39.90], [116.41, 39.94]],
                },
                "legs": [
                    {"distance": 1000, "duration": 200},
                    {"distance": 1000, "duration": 200},
                    {"distance": 1000, "duration": 200},
                ],
            }
        ],
    }

    response = parse_osrm_payload(
        payload,
        open_request("osrm"),
        [A, B, C, D],
        use_trip=True,
        requested_provider="osrm",
        fallback_reason=None,
    )

    assert response.end_mode == "open"
    assert response.optimized is True
    assert response.optimized_indices == [1, 2, 0]
    assert [stop.name for stop in response.stops] == ["A", "C", "D", "B"]
    assert response.stops[-1].role == "destination"
