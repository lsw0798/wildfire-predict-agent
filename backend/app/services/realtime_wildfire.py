from __future__ import annotations

import json
import ssl
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

from app.core.config import Settings, get_settings

DEFAULT_PAGE_NO = 1
DEFAULT_NUM_OF_ROWS = 10
DEFAULT_RESPONSE_TYPE = "xml"
FetchRealtimePayload = Callable[[str], bytes]


def build_realtime_wildfire_url(
    settings: Settings,
    *,
    page_no: int = DEFAULT_PAGE_NO,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    response_type: str = DEFAULT_RESPONSE_TYPE,
) -> str:
    _ = (page_no, num_of_rows, response_type)
    query = urlencode(
        {
            "apiKey": settings.wildfire_api_key,
        }
    )
    return f"{settings.wildfire_api_base_url}?{query}"


def get_realtime_wildfire_status(
    *,
    settings: Settings | None = None,
    fetcher: FetchRealtimePayload | None = None,
    page_no: int = DEFAULT_PAGE_NO,
    num_of_rows: int = DEFAULT_NUM_OF_ROWS,
    response_type: str = DEFAULT_RESPONSE_TYPE,
) -> dict[str, Any]:
    current_settings = settings or get_settings()

    if not current_settings.wildfire_api_key:
        return _fallback_payload(reason="missing_api_key")

    request_url = build_realtime_wildfire_url(
        current_settings,
        page_no=page_no,
        num_of_rows=num_of_rows,
        response_type=response_type,
    )

    fetch = fetcher or _default_fetcher

    try:
        raw_payload = fetch(request_url)
        return _parse_status_payload(raw_payload, request_url)
    except (OSError, RuntimeError, ValueError, URLError) as exc:
        return _fallback_payload(
            reason="request_failed",
            request_url=request_url,
            error=str(exc),
        )


def _default_fetcher(url: str) -> bytes:
    context = _build_ssl_context()
    with urlopen(url, timeout=5, context=context) as response:
        return response.read()


def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _parse_status_payload(raw_payload: bytes, request_url: str) -> dict[str, Any]:
    text = raw_payload.decode("utf-8")

    try:
        parsed = json.loads(text)
        response = parsed.get("response", {})
        header = response.get("header", {})
        body = response.get("body", {})
        items = _normalize_items(body.get("items", []))
        return {
            "available": True,
            "source": "live",
            "reason": None,
            "request_url": request_url,
            "result_code": str(header.get("resultCode", "")),
            "result_message": header.get("resultMsg", ""),
            "items": items,
        }
    except json.JSONDecodeError:
        return _parse_xml_status_payload(text, request_url)


def _normalize_items(raw_items: Any) -> list[dict[str, Any]]:
    if isinstance(raw_items, list):
        return [item for item in raw_items if isinstance(item, dict)]
    if isinstance(raw_items, dict):
        nested_items = raw_items.get("item")
        if isinstance(nested_items, list):
            return [item for item in nested_items if isinstance(item, dict)]
        if isinstance(nested_items, dict):
            return [nested_items]
        return [raw_items]
    return []


def _parse_xml_status_payload(text: str, request_url: str) -> dict[str, Any]:
    root = ElementTree.fromstring(text)
    result_code = root.findtext(".//resultCode", default="")
    result_message = root.findtext(".//resultMsg", default="")
    items: list[dict[str, str]] = []

    for item in root.findall(".//DATA"):
        parsed_item = {
            child.tag: (child.text or "")
            for child in item
        }
        if parsed_item:
            items.append(parsed_item)

    if not items:
        for item in root.findall(".//item"):
            parsed_item = {
                child.tag: (child.text or "")
                for child in item
            }
            if parsed_item:
                items.append(parsed_item)

    return {
        "available": True,
        "source": "live",
        "reason": None,
        "request_url": request_url,
        "result_code": result_code,
        "result_message": result_message,
        "items": items,
    }


def _fallback_payload(
    *,
    reason: str,
    request_url: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "source": "fallback",
        "reason": reason,
        "request_url": request_url,
        "items": [],
    }
    if error is not None:
        payload["error"] = error
    return payload
