from pydantic import BaseModel


class ToolSelectionDecision(BaseModel):
    use_historical: bool
    use_realtime: bool
    selected_tools: list[str]
    reason: str
    mode: str
