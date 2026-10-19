from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["max_intermediates"] == settings.MAX_INTERMEDIATES


def test_places_include_sample_cities() -> None:
    response = client.get("/api/places")
    assert response.status_code == 200
    cities = response.json()["cities"]
    assert cities[0]["id"] == "beijing"
    assert len(cities[0]["places"]) >= 6


def test_optimize_with_local_provider() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "fixed",
            "destination": {"name": "终点", "lat": 0.0, "lng": 0.3},
            "intermediates": [
                {"name": "远点", "lat": 0.0, "lng": 0.25},
                {"name": "近点", "lat": 0.0, "lng": 0.05},
            ],
            "provider": "local",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local"
    assert payload["end_mode"] == "fixed"
    assert payload["optimized_indices"] == [1, 0]
    assert [stop["name"] for stop in payload["stops"]] == ["起点", "近点", "远点", "终点"]
    assert payload["total_distance_meters"] > 0
    assert payload["geometry"][0] == [0.0, 0.0]


def test_optimize_open_route_orders_all_points() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "open",
            "intermediates": [
                {"name": "远点", "lat": 0.0, "lng": 0.25},
                {"name": "近点", "lat": 0.0, "lng": 0.05},
            ],
            "provider": "local",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["end_mode"] == "open"
    assert payload["optimized_indices"] == [1, 0]
    assert [stop["name"] for stop in payload["stops"]] == ["起点", "近点", "远点"]
    assert payload["stops"][-1]["role"] == "destination"


def test_open_route_rejects_fixed_destination() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "open",
            "destination": {"name": "终点", "lat": 0.0, "lng": 0.3},
            "intermediates": [{"name": "点", "lat": 0.0, "lng": 0.1}],
            "provider": "local",
        },
    )
    assert response.status_code == 422
    assert "destination" in response.text


def test_open_route_requires_at_least_one_point() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "open",
            "provider": "local",
        },
    )
    assert response.status_code == 422
    assert "至少需要一个拜访点" in response.text


def test_fixed_route_requires_destination() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "fixed",
            "intermediates": [{"name": "点", "lat": 0.0, "lng": 0.1}],
            "provider": "local",
        },
    )
    assert response.status_code == 422
    assert "需要提供 destination" in response.text


def test_optimize_rejects_too_many_intermediates() -> None:
    intermediates = [
        {"name": f"点 {index}", "lat": 0.0, "lng": index / 100}
        for index in range(settings.MAX_INTERMEDIATES + 1)
    ]
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "fixed",
            "destination": {"name": "终点", "lat": 1.0, "lng": 1.0},
            "intermediates": intermediates,
            "provider": "local",
        },
    )
    assert response.status_code == 422
    assert "最多支持" in response.json()["detail"]


def test_google_provider_requires_key(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", None)
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 0.0, "lng": 0.0},
            "end_mode": "fixed",
            "destination": {"name": "终点", "lat": 1.0, "lng": 1.0},
            "provider": "google",
        },
    )
    assert response.status_code == 400
    assert "GOOGLE_MAPS_API_KEY" in response.json()["detail"]


def test_osrm_rejects_non_driving_mode() -> None:
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 39.90, "lng": 116.40},
            "end_mode": "fixed",
            "destination": {"name": "终点", "lat": 39.94, "lng": 116.41},
            "travel_mode": "WALK",
            "provider": "osrm",
        },
    )
    assert response.status_code == 400
    assert "仅提供驾车路线" in response.json()["detail"]


def test_auto_falls_back_to_local_for_walking(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", None)
    response = client.post(
        "/api/optimize",
        json={
            "origin": {"name": "起点", "lat": 39.90, "lng": 116.40},
            "end_mode": "fixed",
            "destination": {"name": "终点", "lat": 39.94, "lng": 116.41},
            "travel_mode": "WALK",
            "provider": "auto",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local"
    assert "OSRM" in payload["fallback_reason"]


def test_index_page_is_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Optiway" in response.text
