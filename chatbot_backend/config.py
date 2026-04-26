"""
config.py
---------
Centralized settings for the ESG chatbot backend.

LLM provider priority: gemini → groq (using GROQ_API_KEY from .env).
No crash if a key is missing — the provider is simply skipped.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    project_root: Path
    reports_dir: Path
    python_executable: str
    analysis_script_path: Path

    # LLM provider config
    llm_provider: str           # primary provider name  ("gemini" | "groq")
    llm_fallback_provider: str  # fallback provider name ("groq"   | "gemini")

    # Gemini
    gemini_model: str

    # Groq (replaces the old "Grok"/xAI client — uses GROQ_API_KEY)
    groq_model: str

    # Request / session limits
    request_timeout_seconds: int
    max_chat_history: int


def _find_project_root() -> Path:
    cwd = Path.cwd()
    for candidate in (cwd, cwd.parent, cwd.parent.parent):
        if (candidate / "main_langgraph.py").exists():
            return candidate
    return cwd


def load_settings() -> Settings:
    # 1. Load from CWD .env first
    load_dotenv(override=False)

    # 2. Find project root, then load project-level .env files (non-overriding)
    project_root = (
        Path(os.getenv("ESG_PROJECT_ROOT", "")).expanduser().resolve()
        if os.getenv("ESG_PROJECT_ROOT")
        else _find_project_root()
    )
    for env_path in (
        project_root / ".env",
        project_root / "frontend" / ".env.local",
        project_root / "frontend" / ".env",
    ):
        if env_path.exists():
            load_dotenv(env_path, override=False)

    reports_dir = Path(
        os.getenv("ESG_REPORTS_DIR", str(project_root / "reports"))
    ).expanduser().resolve()

    python_executable = os.getenv(
        "ESG_PYTHON_EXECUTABLE", os.getenv("PYTHON", "python")
    )
    analysis_script_path = Path(
        os.getenv("ESG_ANALYSIS_SCRIPT", str(project_root / "main_langgraph.py"))
    ).expanduser().resolve()

    return Settings(
        project_root=project_root,
        reports_dir=reports_dir,
        python_executable=python_executable,
        analysis_script_path=analysis_script_path,
        # Primary: gemini; Fallback: groq  (both use keys from the shared .env)
        llm_provider=os.getenv("ESG_CHAT_LLM_PROVIDER", "gemini").strip().lower(),
        llm_fallback_provider=os.getenv("ESG_CHAT_LLM_FALLBACK", "groq").strip().lower(),
        gemini_model=os.getenv("ESG_CHAT_GEMINI_MODEL", "gemini-2.0-flash"),
        groq_model=os.getenv("ESG_CHAT_GROQ_MODEL", "llama-3.3-70b-versatile"),
        request_timeout_seconds=int(os.getenv("ESG_CHAT_REQUEST_TIMEOUT", "90")),
        max_chat_history=int(os.getenv("ESG_CHAT_HISTORY_TURNS", "10")),
    )
