from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.group_e import ToolSelectionDecision

SelectionDecider = Callable[..., ToolSelectionDecision]


class GroupEToolSelector:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client

    def decide_tools(self, *, lat: float, lon: float, user_type: str) -> ToolSelectionDecision:
        if not self.settings.group_e_enabled:
            return self._fallback_decision(self._format_fallback_reason("feature_disabled"))
        if self.settings.llm_provider == "openai" and not self.settings.openai_api_key:
            return self._fallback_decision(self._format_fallback_reason("missing_openai_api_key"))
        if self.settings.llm_provider != "openai":
            return self._fallback_decision(self._format_fallback_reason(f"unsupported_provider:{self.settings.llm_provider}"))

        try:
            return self._decide_with_openai(lat=lat, lon=lon, user_type=user_type)
        except Exception as exc:  # pragma: no cover - defensive fallback for runtime resilience
            return self._fallback_decision(self._format_fallback_reason(str(exc)))

    def _decide_with_openai(self, *, lat: float, lon: float, user_type: str) -> ToolSelectionDecision:
        client = self.client or self._build_openai_client()
        response = client.responses.create(
            model=self.settings.group_e_model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are a wildfire decision-support source selector. "
                                "Choose whether historical context, realtime context, or both should be queried. "
                                "Return JSON only with keys: use_historical, use_realtime, selected_tools, reason, mode."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"lat={lat}\n"
                                f"lon={lon}\n"
                                f"user_type={user_type}\n"
                                "Available tools: historical, realtime\n"
                                "Use mode='llm'."
                            ),
                        }
                    ],
                },
            ],
        )
        payload = self._extract_response_text(response)
        parsed = json.loads(payload)
        decision = ToolSelectionDecision(**parsed)
        return self._normalize_decision(decision)

    def _build_openai_client(self) -> Any:
        from openai import OpenAI

        return OpenAI(api_key=self.settings.openai_api_key)

    def _extract_response_text(self, response: Any) -> str:
        output = getattr(response, "output", None) or []
        for item in output:
            content = getattr(item, "content", None) or []
            for part in content:
                text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    return text.strip()
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        raise ValueError("OpenAI selector returned no text output")

    def _normalize_decision(self, decision: ToolSelectionDecision) -> ToolSelectionDecision:
        selected_tools = list(dict.fromkeys(decision.selected_tools))
        if decision.use_historical and "historical" not in selected_tools:
            selected_tools.append("historical")
        if decision.use_realtime and "realtime" not in selected_tools:
            selected_tools.append("realtime")
        if not decision.use_historical and "historical" in selected_tools:
            selected_tools.remove("historical")
        if not decision.use_realtime and "realtime" in selected_tools:
            selected_tools.remove("realtime")
        return ToolSelectionDecision(
            use_historical=decision.use_historical,
            use_realtime=decision.use_realtime,
            selected_tools=selected_tools,
            reason=decision.reason,
            mode=decision.mode,
        )

    def _format_fallback_reason(self, raw_reason: str) -> str:
        normalized_reason = raw_reason.strip().lower()

        if raw_reason == "feature_disabled":
            return "LLM 소스 선택 기능이 비활성화되어 규칙 기반 판단으로 계속 분석했습니다."
        if raw_reason == "missing_openai_api_key":
            return "OpenAI API 키가 없어 LLM 소스 선택을 건너뛰고 규칙 기반 판단으로 계속 분석했습니다."
        if normalized_reason.startswith("unsupported_provider:"):
            provider = raw_reason.split(":", 1)[1]
            return f"현재 LLM 제공자({provider})는 소스 선택에 연결되지 않아 규칙 기반 판단으로 계속 분석했습니다."
        if any(
            token in normalized_reason
            for token in (
                "429",
                "usage limit",
                "insufficient_quota",
                "quota",
                "credit",
            )
        ):
            return "OpenAI API 크레딧 또는 사용 한도 문제로 LLM 소스 선택을 건너뛰고 규칙 기반 판단으로 계속 분석했습니다."
        return "LLM 소스 선택 호출에 실패해 규칙 기반 판단으로 계속 분석했습니다."

    def _fallback_decision(self, reason: str) -> ToolSelectionDecision:
        return ToolSelectionDecision(
            use_historical=True,
            use_realtime=True,
            selected_tools=["historical", "realtime"],
            reason=reason,
            mode="rule_fallback",
        )


def get_group_e_tool_selector() -> GroupEToolSelector:
    return GroupEToolSelector(get_settings())


def get_selection_decider() -> SelectionDecider:
    selector = get_group_e_tool_selector()
    return selector.decide_tools
