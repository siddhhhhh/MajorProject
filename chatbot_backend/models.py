from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalysisRunRequest(BaseModel):
    company: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    industry: str = Field(min_length=1)


class ReportResponse(BaseModel):
    status: str
    company: str | None = None
    report_timestamp: str | None = None
    txt_file_name: str | None = None
    json_file_name: str | None = None
    txt_report: str
    json_report: dict[str, Any] | None


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=3)
    question: str = Field(min_length=3)
    provider: str | None = None


class ChatAnswer(BaseModel):
    answer: str
    confidence_explanation: str
    contradictions: list[str]
    citations: list[str]
    scope: str
    intent: str = "unknown"   # detected intent — for frontend display


class ChatResponse(BaseModel):
    status: str
    session_id: str
    answer: ChatAnswer
    provider_used: str


class StreamChatRequest(ChatRequest):
    chunk_size: int = Field(default=40, ge=10, le=200)
