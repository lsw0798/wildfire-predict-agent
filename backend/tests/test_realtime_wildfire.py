from urllib.parse import parse_qs, urlparse

from app.core.config import Settings
from app.services.realtime_wildfire import (
    build_realtime_wildfire_url,
    get_realtime_wildfire_status,
)


def test_build_realtime_wildfire_url_uses_today_fire_endpoint_and_api_key_param():
    settings = Settings(
        _env_file=None,
        wildfire_api_base_url="https://example.com/todayFireGet",
        wildfire_api_key="abc 123",
    )

    url = build_realtime_wildfire_url(
        settings,
        page_no=2,
        num_of_rows=25,
        response_type="json",
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "example.com"
    assert parsed.path == "/todayFireGet"
    assert query == {
        "apiKey": ["abc 123"],
    }


def test_get_realtime_wildfire_status_returns_fallback_when_api_key_missing():
    settings = Settings(_env_file=None, wildfire_api_key="")

    payload = get_realtime_wildfire_status(settings=settings)

    assert payload["available"] is False
    assert payload["source"] == "fallback"
    assert payload["reason"] == "missing_api_key"
    assert payload["request_url"] is None
    assert payload["items"] == []


def test_get_realtime_wildfire_status_parses_root_data_xml_payload_with_injected_fetcher():
    settings = Settings(
        _env_file=None,
        wildfire_api_base_url="https://example.com/todayFireGet",
        wildfire_api_key="live-key",
    )

    def fetcher(url: str) -> bytes:
        assert "apiKey=live-key" in url
        return (
            "<ROOT>"
            "<DATA><SIGUNGU>강릉시</SIGUNGU><STATUS>주의</STATUS></DATA>"
            "<DATA><SIGUNGU>속초시</SIGUNGU><STATUS>관심</STATUS></DATA>"
            "</ROOT>"
        ).encode("utf-8")

    payload = get_realtime_wildfire_status(settings=settings, fetcher=fetcher)

    assert payload["available"] is True
    assert payload["source"] == "live"
    assert payload["reason"] is None
    assert payload["result_code"] == ""
    assert payload["result_message"] == ""
    assert payload["items"] == [
        {"SIGUNGU": "강릉시", "STATUS": "주의"},
        {"SIGUNGU": "속초시", "STATUS": "관심"},
    ]
    assert payload["request_url"] == "https://example.com/todayFireGet?apiKey=live-key"


def test_get_realtime_wildfire_status_still_parses_legacy_json_payload():
    settings = Settings(
        _env_file=None,
        wildfire_api_base_url="https://example.com/todayFireGet",
        wildfire_api_key="live-key",
    )

    def fetcher(url: str) -> bytes:
        assert "apiKey=live-key" in url
        return (
            '{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL_SERVICE"},'
            '"body":{"items":[{"sigungu":"강릉시","status":"주의"}]}}}'
        ).encode("utf-8")

    payload = get_realtime_wildfire_status(settings=settings, fetcher=fetcher)

    assert payload["available"] is True
    assert payload["source"] == "live"
    assert payload["reason"] is None
    assert payload["result_code"] == "00"
    assert payload["result_message"] == "NORMAL_SERVICE"
    assert payload["items"] == [{"sigungu": "강릉시", "status": "주의"}]
    assert payload["request_url"] == "https://example.com/todayFireGet?apiKey=live-key"


def test_get_realtime_wildfire_status_returns_fallback_when_http_call_fails():
    settings = Settings(
        _env_file=None,
        wildfire_api_base_url="https://example.com/todayFireGet",
        wildfire_api_key="live-key",
    )

    def fetcher(_: str) -> bytes:
        raise RuntimeError("network down")

    payload = get_realtime_wildfire_status(settings=settings, fetcher=fetcher)

    assert payload["available"] is False
    assert payload["source"] == "fallback"
    assert payload["reason"] == "request_failed"
    assert payload["items"] == []
    assert payload["error"] == "network down"
    assert payload["request_url"] == "https://example.com/todayFireGet?apiKey=live-key"


def test_get_realtime_wildfire_status_normalizes_nested_items_payload():
    settings = Settings(
        _env_file=None,
        wildfire_api_base_url="https://example.com/todayFireGet",
        wildfire_api_key="live-key",
    )

    def fetcher(_: str) -> bytes:
        return (
            '{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL_SERVICE"},'
            '"body":{"items":{"item":[{"HMDT":"28","WDSP":"5.4","status":"경계"}]}}}}'
        ).encode("utf-8")

    payload = get_realtime_wildfire_status(settings=settings, fetcher=fetcher)

    assert payload["available"] is True
    assert payload["source"] == "live"
    assert payload["items"] == [{"HMDT": "28", "WDSP": "5.4", "status": "경계"}]
