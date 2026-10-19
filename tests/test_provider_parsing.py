from app.config import ProviderName
from app.providers.google import _parse_response as parse_google_response
from app.providers.osrm import _parse_payload as parse_osrm_payload
from app.schemas import OptimizeRequest, Place


def make_request(provider: ProviderName) -> OptimizeRequest:
    return OptimizeRequest(
        origin=Place(name="A", lat=39.90, lng=116.40),
        destination=Place(name="D", lat=39.94, lng=116.41),
        intermediates=[
            Place(name="B", lat=39.91, lng=116.40),
            Place(name="C", lat=39.93, lng=116.41),
        ],
        provider=provider,
    )


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

    response = parse_google_response(payload, make_request("google"), "google", None)

    assert response.provider == "google"
    assert response.optimized is True
    assert response.optimized_indices == [1, 0]
    assert [stop.name for stop in response.stops] == ["A", "C", "B", "D"]
    assert response.total_distance_meters == 1234
    assert response.total_duration_seconds == 456
    assert response.stops[1].leg_distance_meters == 100
    assert response.geometry


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
        make_request("osrm"),
        use_trip=True,
        requested_provider="osrm",
        fallback_reason=None,
    )

    assert response.provider == "osrm"
    assert response.optimized is True
    assert response.optimized_indices == [1, 0]
    assert [stop.name for stop in response.stops] == ["A", "C", "B", "D"]
    assert response.total_distance_meters == 3000
    assert response.total_duration_seconds == 600
    assert response.stops[2].leg_distance_meters == 1000
