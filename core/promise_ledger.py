"""Promise ledger — append-only SQLite of every quantified ESG promise.

The unique-selling-point feature. Tracks each promise longitudinally so we
can label it `NEW` / `IN_PROGRESS` / `KEPT` / `MISSED` / `RETRACTED` /
`DELAYED` on subsequent runs.

Key uniqueness: `(company_lei, metric, target_year)`. Same triple in a
later run is treated as the same promise, even if claim_text varies.

Schema:
    promises(
        id INTEGER PRIMARY KEY,
        company_lei TEXT NOT NULL,
        metric TEXT NOT NULL,
        target_year INTEGER NOT NULL,
        target_value REAL,
        target_unit TEXT,
        baseline_year INTEGER,
        baseline_value REAL,
        claim_text TEXT,
        source_url TEXT,
        report_id TEXT,
        status_label TEXT,
        created_utc TEXT,
        last_seen_utc TEXT,
        seen_count INTEGER DEFAULT 1
    )

Read API:
    PromiseLedger().status_for_promise(company_lei, metric, target_year, target_value)
    PromiseLedger().promises_for(company_lei) -> List[PromiseRow]

Write API:
    PromiseLedger().record(company_lei, metric, target_year, target_value, ...)

The ledger lives at data/promise_ledger.db. Wipe + replay supported via
core/promise_ledger_seed.py for testing.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "promise_ledger.db"
_DB_LOCK = threading.Lock()


@dataclass
class PromiseRow:
    id: int
    company_lei: str
    metric: str
    target_year: int
    target_value: Optional[float]
    target_unit: Optional[str]
    baseline_year: Optional[int]
    baseline_value: Optional[float]
    claim_text: str
    source_url: Optional[str]
    report_id: Optional[str]
    status_label: str
    created_utc: str
    last_seen_utc: str
    seen_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":             self.id,
            "company_lei":    self.company_lei,
            "metric":         self.metric,
            "target_year":    self.target_year,
            "target_value":   self.target_value,
            "target_unit":    self.target_unit,
            "baseline_year":  self.baseline_year,
            "baseline_value": self.baseline_value,
            "claim_text":     self.claim_text,
            "source_url":     self.source_url,
            "report_id":      self.report_id,
            "status_label":   self.status_label,
            "created_utc":    self.created_utc,
            "last_seen_utc":  self.last_seen_utc,
            "seen_count":     self.seen_count,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS promises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_lei TEXT NOT NULL,
    metric TEXT NOT NULL,
    target_year INTEGER NOT NULL,
    target_value REAL,
    target_unit TEXT,
    baseline_year INTEGER,
    baseline_value REAL,
    claim_text TEXT,
    source_url TEXT,
    report_id TEXT,
    status_label TEXT,
    created_utc TEXT NOT NULL,
    last_seen_utc TEXT NOT NULL,
    seen_count INTEGER DEFAULT 1,
    UNIQUE(company_lei, metric, target_year)
);
CREATE INDEX IF NOT EXISTS idx_promises_company ON promises(company_lei);
"""


class PromiseLedger:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with _DB_LOCK, sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _row_to_promise(self, row: sqlite3.Row) -> PromiseRow:
        return PromiseRow(
            id=row[0], company_lei=row[1], metric=row[2], target_year=row[3],
            target_value=row[4], target_unit=row[5],
            baseline_year=row[6], baseline_value=row[7],
            claim_text=row[8], source_url=row[9], report_id=row[10],
            status_label=row[11],
            created_utc=row[12], last_seen_utc=row[13], seen_count=row[14],
        )

    def promises_for(self, company_lei: str) -> List[PromiseRow]:
        if not company_lei:
            return []
        with _DB_LOCK, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM promises WHERE company_lei=? "
                "ORDER BY target_year ASC", (company_lei,),
            ).fetchall()
        return [self._row_to_promise(r) for r in rows]

    def find(self, company_lei: str, metric: str, target_year: int) -> Optional[PromiseRow]:
        with _DB_LOCK, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM promises WHERE company_lei=? AND metric=? AND target_year=?",
                (company_lei, metric, target_year),
            ).fetchone()
        return self._row_to_promise(row) if row else None

    def find_latest_for_metric(self, company_lei: str, metric: str) -> Optional[PromiseRow]:
        """Find the most recently-recorded promise for (lei, metric) regardless of target_year.

        Used by DELAYED detection — a fresh promise with a later target_year
        for the same metric indicates the company pushed back the timeline.
        """
        with _DB_LOCK, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM promises WHERE company_lei=? AND metric=? "
                "ORDER BY last_seen_utc DESC LIMIT 1",
                (company_lei, metric),
            ).fetchone()
        return self._row_to_promise(row) if row else None

    def record(
        self, *,
        company_lei: str,
        metric: str,
        target_year: int,
        target_value: Optional[float],
        target_unit: Optional[str] = None,
        baseline_year: Optional[int] = None,
        baseline_value: Optional[float] = None,
        claim_text: str = "",
        source_url: Optional[str] = None,
        report_id: Optional[str] = None,
        status_label: str = "NEW",
    ) -> PromiseRow:
        """Insert-or-update by (company_lei, metric, target_year)."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _DB_LOCK, self._connect() as conn:
            existing = conn.execute(
                "SELECT id, seen_count, created_utc FROM promises "
                "WHERE company_lei=? AND metric=? AND target_year=?",
                (company_lei, metric, target_year),
            ).fetchone()
            if existing:
                pid, seen, created = existing
                conn.execute(
                    "UPDATE promises SET target_value=COALESCE(?, target_value), "
                    "target_unit=COALESCE(?, target_unit), "
                    "baseline_year=COALESCE(?, baseline_year), "
                    "baseline_value=COALESCE(?, baseline_value), "
                    "claim_text=COALESCE(?, claim_text), "
                    "source_url=COALESCE(?, source_url), "
                    "report_id=COALESCE(?, report_id), "
                    "status_label=?, last_seen_utc=?, seen_count=? "
                    "WHERE id=?",
                    (target_value, target_unit, baseline_year, baseline_value,
                     claim_text or None, source_url, report_id,
                     status_label, now, seen + 1, pid),
                )
            else:
                conn.execute(
                    "INSERT INTO promises ("
                    "company_lei, metric, target_year, target_value, target_unit, "
                    "baseline_year, baseline_value, claim_text, source_url, "
                    "report_id, status_label, created_utc, last_seen_utc, seen_count"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                    (company_lei, metric, target_year, target_value, target_unit,
                     baseline_year, baseline_value, claim_text, source_url,
                     report_id, status_label, now, now),
                )
            conn.commit()
        return self.find(company_lei, metric, target_year)


# ── Promise extraction from sub-claims ────────────────────────────────────────
_NETZERO_RE = re.compile(r"net[- ]?zero|carbon[- ]?neutral|climate positive", re.I)
_PCT_REDUCTION_RE = re.compile(
    r"(?:reduce|reduction|decrease|cut|lower|by)\s*[^.]{0,40}?"
    r"(?P<pct>\d{1,3}(?:\.\d+)?)\s*%",
    re.I,
)
_TARGET_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_SCOPE_RE = re.compile(r"\bscope\s*([123])\b", re.I)


def _extract_metric_and_target(text: str) -> Optional[Dict[str, Any]]:
    """Pull (metric, target_year, target_value, target_unit) from a sub-claim."""
    if not text:
        return None
    txt = text.lower()

    # Net-zero / carbon-neutral kind
    if _NETZERO_RE.search(text):
        m = _TARGET_YEAR_RE.search(text)
        if m:
            return {
                "metric":        "net_zero_emissions",
                "target_year":   int(m.group(1)),
                "target_value":  0.0,
                "target_unit":   "tCO2e",
            }

    # Percent-reduction kind
    pm = _PCT_REDUCTION_RE.search(text)
    ym = _TARGET_YEAR_RE.search(text)
    if pm and ym:
        sm = _SCOPE_RE.search(text)
        scope = f"scope{sm.group(1)}" if sm else "ghg_emissions"
        return {
            "metric":      f"{scope}_pct_reduction",
            "target_year": int(ym.group(1)),
            "target_value": float(pm.group("pct")),
            "target_unit": "percent",
        }

    return None


def extract_promises_from_subclaims(
    sub_claims: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Pull quantified-promise rows from a claim_decomposition output."""
    out: List[Dict[str, Any]] = []
    for sc in sub_claims:
        if not isinstance(sc, dict):
            continue
        if not sc.get("measurable"):
            continue
        text = sc.get("text") or sc.get("claim") or ""
        if not text:
            continue
        extracted = _extract_metric_and_target(text)
        if not extracted:
            continue
        extracted["claim_text"] = text
        extracted["sub_claim_id"] = sc.get("id")
        out.append(extracted)
    return out
