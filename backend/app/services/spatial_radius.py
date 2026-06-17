from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM = 50.0
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RadiusBounds:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


def cardinal_point(
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    direction: Literal["north", "south", "east", "west"],
) -> GeoPoint:
    latitude_offset = math.degrees(radius_km / EARTH_RADIUS_KM)
    longitude_scale = max(math.cos(math.radians(latitude)), 1e-12)
    longitude_offset = math.degrees(radius_km / (EARTH_RADIUS_KM * longitude_scale))

    if direction == "north":
        return GeoPoint(latitude=latitude + latitude_offset, longitude=longitude)
    if direction == "south":
        return GeoPoint(latitude=latitude - latitude_offset, longitude=longitude)
    if direction == "east":
        return GeoPoint(latitude=latitude, longitude=longitude + longitude_offset)
    return GeoPoint(latitude=latitude, longitude=longitude - longitude_offset)


def radius_bounds(*, latitude: float, longitude: float, radius_km: float) -> RadiusBounds:
    north = cardinal_point(latitude=latitude, longitude=longitude, radius_km=radius_km, direction="north")
    south = cardinal_point(latitude=latitude, longitude=longitude, radius_km=radius_km, direction="south")
    east = cardinal_point(latitude=latitude, longitude=longitude, radius_km=radius_km, direction="east")
    west = cardinal_point(latitude=latitude, longitude=longitude, radius_km=radius_km, direction="west")
    return RadiusBounds(
        min_lat=south.latitude,
        max_lat=north.latitude,
        min_lon=west.longitude,
        max_lon=east.longitude,
    )
