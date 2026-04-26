from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import time


@dataclass(slots=True)
class ChatTurn:
    role: str
    content: str
    ts: float


@dataclass(slots=True)
class SessionData:
    turns: list[ChatTurn] = field(default_factory=list)
    updated_at: float = field(default_factory=time)


class SessionMemoryStore:
    def __init__(self, max_turns: int = 10, ttl_seconds: int = 60 * 60 * 6) -> None:
        self._max_turns = max_turns
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, SessionData] = {}
        self._lock = Lock()

    def _cleanup(self) -> None:
        now = time()
        stale = [key for key, value in self._store.items() if now - value.updated_at > self._ttl_seconds]
        for key in stale:
            self._store.pop(key, None)

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            self._cleanup()
            session = self._store.get(session_id)
            if not session:
                return []
            return [{"role": turn.role, "content": turn.content} for turn in session.turns]

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self._cleanup()
            session = self._store.setdefault(session_id, SessionData())
            session.turns.append(ChatTurn(role=role, content=content, ts=time()))
            if len(session.turns) > self._max_turns * 2:
                session.turns = session.turns[-self._max_turns * 2 :]
            session.updated_at = time()
