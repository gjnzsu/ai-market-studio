from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, Any, Literal
from datetime import date as _date_type
from backend.config import settings


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


AgentMode = Literal["workflow"]


class ChatClientContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(default="ai-market-studio", alias="applicationId")
    project_id: str = Field(default="fx-market-insight", alias="projectId")
    team_id: str = Field(default="markets", alias="teamId")
    user_id: Optional[str] = Field(default=None, alias="userId")
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    conversation_id: Optional[str] = Field(default=None, alias="conversationId")
    request_id: Optional[str] = Field(default=None, alias="requestId")
    use_case: Optional[str] = Field(default=None, alias="useCase")
    feature: Optional[str] = None
    environment: str = "prod"


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    agent_mode: AgentMode = "workflow"
    client_context: Optional[ChatClientContext] = Field(
        default=None,
        alias="clientContext",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        return v


class ChatResponse(BaseModel):
    reply: str
    data: Optional[Any] = None
    tool_used: Optional[str] = None


# ---------------------------------------------------------------------------
# Feature 02 — Historical rates & dashboard models
# ---------------------------------------------------------------------------

class HistoricalRatesRequest(BaseModel):
    base:       str       = Field(..., min_length=3, max_length=3)
    targets:    list[str] = Field(..., min_length=1, max_length=10)
    start_date: str       = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date:   str       = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("base", "targets", mode="before")
    @classmethod
    def upper(cls, v):
        if isinstance(v, list):
            return [x.upper() for x in v]
        return v.upper()

    @model_validator(mode="after")
    def check_date_range(self):
        start = _date_type.fromisoformat(self.start_date)
        end   = _date_type.fromisoformat(self.end_date)
        if (end - start).days >= settings.max_historical_days:
            raise ValueError(
                f"Date range exceeds {settings.max_historical_days}-day limit"
            )
        return self


class DailyRates(BaseModel):
    date:  str              # "YYYY-MM-DD"
    rates: dict[str, float] # {"EUR": 0.92}


class HistoricalRatesResponse(BaseModel):
    base:       str
    start_date: str
    end_date:   str
    series:     list[DailyRates]  # sorted ascending
    cached:     bool = False


class DashboardPanelConfig(BaseModel):
    panel_id:   str
    panel_type: Literal["line_trend", "bar_comparison", "stat_summary"]
    base:       str
    targets:    list[str]
    start_date: str
    end_date:   str


class DashboardConfig(BaseModel):
    dashboard_id:   str
    dashboard_type: Literal["trend", "comparison", "mixed"]
    panels: list[DashboardPanelConfig] = Field(..., min_length=1, max_length=9)


class DashboardDataResponse(BaseModel):
    dashboard_id: str
    panels: list[dict]  # {panel_id, panel_type, data: HistoricalRatesResponse}


# ---------------------------------------------------------------------------
# Feature 03 — Export to PDF
# ---------------------------------------------------------------------------

class ExportPdfRequest(BaseModel):
    reply: str
    data: Optional[Any] = None
    tool_used: Optional[str] = None
