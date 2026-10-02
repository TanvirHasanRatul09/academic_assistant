from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class AssistantQuery(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=6)


class AssistantAction(BaseModel):
    label: str
    url: str = Field(max_length=2048, pattern=r"^https://")
    kind: Literal["pdf", "attachment", "classroom"]


class AssistantSource(BaseModel):
    title: str
    course_name: str
    source_url: str | None = Field(default=None, max_length=2048)
    event_type: str
    item_subtype: str = "other"
    completed: bool | None = None
    starts_at: datetime | None
    due_at: datetime | None
    actions: list[AssistantAction] = Field(default_factory=list, max_length=10)


GeminiStatus = Literal[
    "configured",
    "not_configured",
    "reachable",
    "invalid_credentials",
    "rate_limited",
    "quota_exceeded",
    "timeout",
    "network_error",
    "model_unavailable",
    "provider_error",
    "blocked_response",
    "malformed_response",
]


class GeminiHealth(BaseModel):
    status: GeminiStatus
    model: str
    message: str
    request_id: str


class AssistantOutput(BaseModel):
    answer: str
    mode: Literal["gemini", "local"]
    gemini_status: GeminiStatus
    tool: Literal[
        "get_tasks_by_date", "get_upcoming_deadlines", "get_exams", "search_academic_content"
    ]
    sources: list[AssistantSource]
    last_sync_at: datetime | None
    data_available: bool
    answer_status: Literal[
        "exact_match",
        "multiple_matches",
        "ambiguous_course",
        "no_exact_match",
        "partial_sync",
        "stale_data",
    ] = "exact_match"
    intent: str = "general_information"
    item: "AssistantItem | None" = None
    possible_matches: list["AssistantItem"] = Field(default_factory=list, max_length=10)


class AssistantItem(BaseModel):
    title: str
    course_name: str
    item_subtype: str
    completed: bool | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None
    source_kind: Literal["classroom", "manual"]
    source_url: str | None = Field(default=None, max_length=2048)


AssistantOutput.model_rebuild()
