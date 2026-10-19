from typing import Literal

from pydantic import BaseModel, Field

from app.config import ProviderName

TravelMode = Literal["DRIVE", "WALK", "BICYCLE"]
StopRole = Literal["origin", "intermediate", "destination"]
ActualProvider = Literal["google", "osrm", "local"]


class Place(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class OptimizeRequest(BaseModel):
    origin: Place
    destination: Place
    intermediates: list[Place] = Field(default_factory=list)
    travel_mode: TravelMode = "DRIVE"
    optimize: bool = True
    provider: ProviderName | None = None


class StopResult(BaseModel):
    name: str
    lat: float
    lng: float
    role: StopRole
    leg_distance_meters: float = 0.0
    leg_duration_seconds: float = 0.0
    cumulative_duration_seconds: float = 0.0


class OptimizeResponse(BaseModel):
    provider: ActualProvider
    provider_label: str
    requested_provider: ProviderName
    optimized: bool
    fallback_reason: str | None = None
    note: str | None = None
    stops: list[StopResult]
    total_distance_meters: float
    total_duration_seconds: float
    # [longitude, latitude] pairs, ready for Leaflet after swapping.
    geometry: list[list[float]]
    # Original indices of the intermediate stops, in optimized order.
    optimized_indices: list[int]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    google_configured: bool
    default_provider: ProviderName
    osrm_base_url: str
    max_intermediates: int
    map_tile_url: str
    map_tile_attribution: str
    map_tile_max_zoom: int


class PlaceOption(BaseModel):
    id: str
    name: str
    lat: float
    lng: float


class CityPlaces(BaseModel):
    id: str
    name: str
    center: list[float]
    places: list[PlaceOption]


class PlacesResponse(BaseModel):
    cities: list[CityPlaces]
