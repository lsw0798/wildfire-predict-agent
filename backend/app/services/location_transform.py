"""좌표계 변환 유틸리티."""

from __future__ import annotations

from math import cos, degrees, isfinite, radians, sin, sqrt, tan

_GRS80_SEMI_MAJOR_AXIS = 6378137.0
_GRS80_FLATTENING = 1 / 298.257222101
_LATITUDE_OF_ORIGIN = radians(38.0)
_CENTRAL_MERIDIAN = radians(127.5)
_SCALE_FACTOR = 0.9996
_FALSE_EASTING = 1_000_000.0
_FALSE_NORTHING = 2_000_000.0

_GRS80_SEMI_MINOR_AXIS = _GRS80_SEMI_MAJOR_AXIS * (1 - _GRS80_FLATTENING)
_ECCENTRICITY_SQUARED = (
    _GRS80_SEMI_MAJOR_AXIS**2 - _GRS80_SEMI_MINOR_AXIS**2
) / _GRS80_SEMI_MAJOR_AXIS**2
_SECOND_ECCENTRICITY_SQUARED = _ECCENTRICITY_SQUARED / (1 - _ECCENTRICITY_SQUARED)
_E4 = _ECCENTRICITY_SQUARED**2
_E6 = _E4 * _ECCENTRICITY_SQUARED
_E1 = (1 - sqrt(1 - _ECCENTRICITY_SQUARED)) / (1 + sqrt(1 - _ECCENTRICITY_SQUARED))


def _meridional_arc(latitude_radians: float) -> float:
    return _GRS80_SEMI_MAJOR_AXIS * (
        (1 - _ECCENTRICITY_SQUARED / 4 - 3 * _E4 / 64 - 5 * _E6 / 256) * latitude_radians
        - (3 * _ECCENTRICITY_SQUARED / 8 + 3 * _E4 / 32 + 45 * _E6 / 1024) * sin(2 * latitude_radians)
        + (15 * _E4 / 256 + 45 * _E6 / 1024) * sin(4 * latitude_radians)
        - (35 * _E6 / 3072) * sin(6 * latitude_radians)
    )


_MERIDIONAL_ARC_AT_ORIGIN = _meridional_arc(_LATITUDE_OF_ORIGIN)


def kgd2002_unified_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """KGD2002 Unified(EPSG:5179) 좌표를 WGS84 위경도로 변환한다."""
    if not isfinite(easting) or not isfinite(northing):
        raise ValueError("좌표는 유한한 실수여야 합니다.")

    x = float(easting) - _FALSE_EASTING
    y = float(northing) - _FALSE_NORTHING

    meridional_arc = _MERIDIONAL_ARC_AT_ORIGIN + y / _SCALE_FACTOR
    mu = meridional_arc / (
        _GRS80_SEMI_MAJOR_AXIS * (1 - _ECCENTRICITY_SQUARED / 4 - 3 * _E4 / 64 - 5 * _E6 / 256)
    )

    footprint_latitude = (
        mu
        + (3 * _E1 / 2 - 27 * _E1**3 / 32) * sin(2 * mu)
        + (21 * _E1**2 / 16 - 55 * _E1**4 / 32) * sin(4 * mu)
        + (151 * _E1**3 / 96) * sin(6 * mu)
        + (1097 * _E1**4 / 512) * sin(8 * mu)
    )

    sin_fp = sin(footprint_latitude)
    cos_fp = cos(footprint_latitude)
    tan_fp = tan(footprint_latitude)

    radius_n = _GRS80_SEMI_MAJOR_AXIS / sqrt(1 - _ECCENTRICITY_SQUARED * sin_fp**2)
    radius_r = _GRS80_SEMI_MAJOR_AXIS * (1 - _ECCENTRICITY_SQUARED) / (1 - _ECCENTRICITY_SQUARED * sin_fp**2) ** 1.5
    c1 = _SECOND_ECCENTRICITY_SQUARED * cos_fp**2
    t1 = tan_fp**2
    d = x / (radius_n * _SCALE_FACTOR)

    latitude = footprint_latitude - (
        radius_n
        * tan_fp
        / radius_r
        * (
            d**2 / 2
            - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * _SECOND_ECCENTRICITY_SQUARED) * d**4 / 24
            + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * _SECOND_ECCENTRICITY_SQUARED - 3 * c1**2)
            * d**6
            / 720
        )
    )
    longitude = _CENTRAL_MERIDIAN + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * _SECOND_ECCENTRICITY_SQUARED + 24 * t1**2) * d**5 / 120
    ) / cos_fp

    return degrees(latitude), degrees(longitude)


def is_within_korea_bounds(latitude: float, longitude: float) -> bool:
    """대한민국 영역 검증에 사용할 수 있는 단순 위경도 경계 체크."""
    if not isfinite(latitude) or not isfinite(longitude):
        return False

    return 33.0 <= float(latitude) <= 38.8 and 124.5 <= float(longitude) <= 131.0
