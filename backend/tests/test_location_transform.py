import pytest

from app.services.location_transform import is_within_korea_bounds, kgd2002_unified_to_wgs84


def test_kgd2002_unified_to_wgs84_converts_seoul_city_hall():
    latitude, longitude = kgd2002_unified_to_wgs84(953901.165, 1952032.081)

    assert latitude == pytest.approx(37.5665, abs=1e-5)
    assert longitude == pytest.approx(126.9780, abs=1e-5)


def test_kgd2002_unified_to_wgs84_converts_busan_city_hall():
    latitude, longitude = kgd2002_unified_to_wgs84(1143467.380, 1688281.982)

    assert latitude == pytest.approx(35.1796, abs=1e-5)
    assert longitude == pytest.approx(129.0756, abs=1e-5)


def test_is_within_korea_bounds_accepts_mainland_and_rejects_outside():
    assert is_within_korea_bounds(37.5665, 126.9780) is True
    assert is_within_korea_bounds(35.1796, 129.0756) is True
    assert is_within_korea_bounds(35.6764, 139.6500) is False
