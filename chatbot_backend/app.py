from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from chatbot_backend.config import load_settings
from chatbot_backend.memory import SessionMemoryStore
from chatbot_backend.models import (
    AnalysisRunRequest,
    ChatRequest,
    ChatResponse,
    ReportResponse,
    StreamChatRequest,
)
from chatbot_backend.service import ESGChatService

settings = load_settings()
memory_store = SessionMemoryStore(max_turns=settings.max_chat_history)
service = ESGChatService(settings=settings, memory_store=memory_store)

app = FastAPI(title="ESG Analyst Copilot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run-analysis", response_model=ReportResponse)
def run_analysis(payload: AnalysisRunRequest) -> ReportResponse:
    result = service.run_analysis(
        company=payload.company, claim=payload.claim, industry=payload.industry
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result)
    return ReportResponse(**result)


@app.get("/report", response_model=ReportResponse)
def get_latest_report(company: str | None = Query(default=None)) -> ReportResponse:
    result = service.get_latest_report(company=company)
    if result is None:
        raise HTTPException(status_code=404, detail="No report file found")
    return ReportResponse(**result)


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        answer, provider_used = service.answer(
            session_id=payload.session_id,
            question=payload.question,
            provider=payload.provider,
            report_id=payload.report_id,
            company=payload.company,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}") from exc

    return ChatResponse(
        status="success",
        session_id=payload.session_id,
        answer=answer,
        provider_used=provider_used,
    )


@app.post("/chat/stream")
def chat_stream(payload: StreamChatRequest):
    try:
        answer, provider_used = service.answer(
            session_id=payload.session_id,
            question=payload.question,
            provider=payload.provider,
            report_id=payload.report_id,
            company=payload.company,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}") from exc

    answer_text = answer.get("answer", "")
    chunk_size = payload.chunk_size

    def event_stream():
        meta = {
            "session_id":              payload.session_id,
            "provider_used":           provider_used,
            "intent":                  answer.get("intent", "unknown"),
            "citations":               answer.get("citations", []),
            "contradictions":          answer.get("contradictions", []),
            "confidence_explanation":  answer.get("confidence_explanation", ""),
            "scope":                   answer.get("scope", "ESG_ANALYSIS"),
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"

        for index in range(0, len(answer_text), chunk_size):
            part = answer_text[index : index + chunk_size]
            yield f"event: message\ndata: {json.dumps({'delta': part})}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
