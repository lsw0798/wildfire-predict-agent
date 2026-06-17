from app.core.config import Settings
from app.services.group_e_selector import GroupEToolSelector


def build_selector() -> GroupEToolSelector:
    return GroupEToolSelector(
        Settings(
            group_e_enabled=True,
            llm_provider="openai",
            openai_api_key="test-key",
        )
    )


def test_group_e_selector_converts_openai_quota_error_to_user_friendly_rule_fallback(monkeypatch):
    selector = build_selector()

    def raise_quota_error(*, lat: float, lon: float, user_type: str):
        raise RuntimeError("API call failed after 3 retries: HTTP 429: The usage limit has been reached")

    monkeypatch.setattr(selector, "_decide_with_openai", raise_quota_error)

    decision = selector.decide_tools(lat=37.5665, lon=126.9780, user_type="공무원")

    assert decision.mode == "rule_fallback"
    assert decision.selected_tools == ["historical", "realtime"]
    assert "크레딧" in decision.reason or "한도" in decision.reason
    assert "429" not in decision.reason
    assert "usage limit" not in decision.reason.lower()


def test_group_e_selector_converts_missing_openai_key_to_user_friendly_rule_fallback():
    selector = GroupEToolSelector(
        Settings(
            group_e_enabled=True,
            llm_provider="openai",
            openai_api_key="",
        )
    )

    decision = selector.decide_tools(lat=37.5665, lon=126.9780, user_type="공무원")

    assert decision.mode == "rule_fallback"
    assert "API 키" in decision.reason
    assert "missing" not in decision.reason.lower()
