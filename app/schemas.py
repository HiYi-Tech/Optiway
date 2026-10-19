from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.config import ProviderName

TravelMode = Literal["DRIVE", "WALK", "BICYCLE"]
StopRole = Literal["origin", "intermediate", "destination"]
ActualProvider = Literal["google", "osrm", "local"]
EndMode = Literal["fixed", "open"]


class Place(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class OptimizeRequest(BaseModel):
    origin: Place
    # open: only the origin is fixed; every other point is ordered by the algorithm.
    # fixed: origin and destination are fixed; only intermediates are reordered.
    end_mode: EndMode = "open"
    destination: Place | None = None
    intermediates: list[Place] = Field(default_factory=list)
    travel_mode: TravelMode = "DRIVE"
    optimize: bool = True
    provider: ProviderName | None = None

    @model_validator(mode="after")
    def _validate_end_mode(self) -> Self:
        if self.end_mode == "open":
            if self.destination is not None:
                raise ValueError(
                    "开放路线模式请将所有非起点地点放入 intermediates，不要提供 destination。"
                )
            if not self.intermediates:
                raise ValueError("开放路线模式至少需要一个拜访点。")
        elif self.destination is None:
            raise ValueError("固定终点模式需要提供 destination。")
        return self


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
    end_mode: EndMode
    optimized: bool
    fallback_reason: str | None = None
    note: str | None = None
    stops: list[StopResult]
    total_distance_meters: float
    total_duration_seconds: float
    # [longitude, latitude] pairs, ready for Leaflet after swapping.
    geometry: list[list[float]]
    # Original indices of the ordered non-origin points.
    # open mode: includes the algorithm-chosen final point.
    # fixed mode: only intermediates (the fixed destination is excluded).
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
