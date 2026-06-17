import pytest

from app.services.spatial_radius import (
    DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM,
    cardinal_point,
    radius_bounds,
)


def test_default_historical_analysis_radius_is_documented_constant():
    assert DEFAULT_HISTORICAL_ANALYSIS_RADIUS_KM == 50.0


def test_radius_bounds_expand_in_all_cardinal_directions():
    bounds = radius_bounds(latitude=37.5665, longitude=126.9780, radius_km=10.0)

    assert bounds.min_lat < 37.5665 < bounds.max_lat
    assert bounds.min_lon < 126.9780 < bounds.max_lon


@pytest.mark.parametrize(
    ("direction", "latitude_cmp", "longitude_cmp"),
    [
        ("north", "gt", "eq"),
        ("south", "lt", "eq"),
        ("east", "eq", "gt"),
        ("west", "eq", "lt"),
    ],
)
def test_cardinal_point_moves_expected_axis(direction: str, latitude_cmp: str, longitude_cmp: str):
    origin_lat = 37.5665
    origin_lon = 126.9780
    point = cardinal_point(latitude=origin_lat, longitude=origin_lon, radius_km=10.0, direction=direction)

    if latitude_cmp == "gt":
        assert point.latitude > origin_lat
    elif latitude_cmp == "lt":
        assert point.latitude < origin_lat
    else:
        assert point.latitude == pytest.approx(origin_lat, abs=1e-6)

    if longitude_cmp == "gt":
        assert point.longitude > origin_lon
    elif longitude_cmp == "lt":
        assert point.longitude < origin_lon
    else:
        assert point.longitude == pytest.approx(origin_lon, abs=1e-6)