"""
server.pyuvico
---------
ESGLens FastAPI backend server.
Runs on port 8000 and exposes:
  - REST API:   /api/*
  - WebSocket:  /ws/pipeline/{analysis_id}
  - Health:     /health

Start with:
  rn server:app --reload --port 8000

The existing pipeline (main_langgraph.py) is NOT modified.
"""
from __future__ import annotations

import os

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router

app = FastAPI(
    title="ESGLens API",
    version="1.0.0",
    description="ESG Greenwashing Detection API — powered by LangGraph multi-agent pipeline",
)

# ── CORS ────────────────────────────────────────────────────────────────────
# Allow the ESGLens frontend on port 3001 (and the older frontend on 3000/8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount all routes ─────────────────────────────────────────────────────────
app.include_router(api_router)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "ESGLens API", "version": "1.0.0"}


# ── Dev runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
