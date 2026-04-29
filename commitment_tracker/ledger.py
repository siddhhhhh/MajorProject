import datetime as dt
import math
import os
import sqlite3
from functools import lru_cache
from typing import Any, Dict, List, Optional

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional local dependency
    SentenceTransformer = None


@lru_cache(maxsize=1)
def _load_semantic_model():
    if SentenceTransformer is None:
        return None
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None


class CommitmentLedger:
    def __init__(self, db_path: str = "data/commitment_ledger.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commitments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    run_date DATE NOT NULL,
                    claim_text TEXT NOT NULL,
                    sub_claim_id TEXT,
                    commitment_type TEXT,
                    target_year INTEGER,
                    target_metric TEXT,
                    target_value REAL,
                    target_direction TEXT,
                    baseline_year INTEGER,
                    baseline_value REAL,
                    current_value REAL,
                    progress_pct REAL,
                    status TEXT,
                    evidence_url TEXT,
                    confidence REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commitment_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    original_commitment_id INTEGER,
                    revision_date DATE,
                    original_text TEXT,
                    revised_text TEXT,
                    revision_type TEXT,
                    severity_score REAL,
                    explanation TEXT,
                    FOREIGN KEY(original_commitment_id) REFERENCES commitments(id)
                )
                """
            )
            conn.commit()

    def update_from_subclaims(
        self,
        company: str,
        run_id: str,
        run_date: str,
        sub_claims: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        revisions: List[Dict[str, Any]] = []
        inserted_ids: List[int] = []

        with self._connect() as conn:
            historical = conn.execute(
                "SELECT * FROM commitments WHERE company=? ORDER BY run_date DESC",
                (company,),
            ).fetchall()

            historical_rows = [dict(r) for r in historical]

            for sc in sub_claims or []:
                text = str(sc.get("text") or "").strip()
                if not text:
                    continue
                match = self._find_best_match(text, historical_rows)

                commitment_id = None
                if match and match.get("similarity", 0.0) > 0.75:
                    commitment_id = int(match["id"])
                    rev = self._classify_revision(match.get("claim_text", ""), text)
                    if rev["revision_type"] not in {"no_change", "strengthened"}:
                        conn.execute(
                            """
                            INSERT INTO commitment_revisions (
                                company, original_commitment_id, revision_date, original_text,
                                revised_text, revision_type, severity_score, explanation
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                company,
                                commitment_id,
                                run_date,
                                match.get("claim_text", ""),
                                text,
                                rev["revision_type"],
                                rev["severity"],
                                rev["explanation"],
                            ),
                        )
                        revisions.append(rev)

                target_year = self._extract_target_year(text)
                ctype = str(sc.get("type") or "policy_claim")
                evidence_url = self._best_evidence_url(sc.get("id"), evidence)

                cur = conn.execute(
                    """
                    INSERT INTO commitments (
                        company, run_id, run_date, claim_text, sub_claim_id, commitment_type,
                        target_year, target_metric, target_value, target_direction,
                        baseline_year, baseline_value, current_value, progress_pct, status,
                        evidence_url, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company,
                        run_id,
                        run_date,
                        text,
                        sc.get("id"),
                        ctype,
                        target_year,
                        None,
                        None,
                        self._target_direction(text),
                        None,
                        None,
                        None,
                        None,
                        "on_track",
                        evidence_url,
                        0.65,
                    ),
                )
                inserted_ids.append(int(cur.lastrowid))

            conn.commit()

        promise_score = self.compute_promise_degradation_score(company)

        return {
            "db_path": self.db_path,
            "inserted_commitments": len(inserted_ids),
            "revision_events": revisions,
            "promise_degradation_score": promise_score,
        }

    def compute_promise_degradation_score(self, company: str) -> float:
        today = dt.date.today()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT revision_date, revision_type, severity_score FROM commitment_revisions WHERE company=?",
                (company,),
            ).fetchall()

        score = 0.0
        for row in rows:
            rev_date = self._parse_date(row["revision_date"]) if row["revision_date"] else today
            age_years = max(0.0, (today - rev_date).days / 365.0)
            recency_weight = math.exp(-0.3 * age_years)
            type_penalty = {
                "claim_dropped": 30,
                "target_weakened": 20,
                "deadline_extended": 15,
                "scope_narrowed": 12,
                "reframed": 8,
                "baseline_reset": 10,
            }.get(str(row["revision_type"] or ""), 0)
            sev = float(row["severity_score"] or 0.0)
            score += type_penalty * recency_weight * (sev / 100.0)

        return round(min(score, 100.0), 2)

    def _parse_date(self, raw: Any) -> dt.date:
        txt = str(raw)
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(txt[:10], fmt).date()
            except Exception:
                continue
        return dt.date.today()

    def _find_best_match(self, text: str, rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best = None
        best_sim = 0.0
        for row in rows:
            old_text = str(row.get("claim_text") or "")
            if not text.strip() or not old_text.strip():
                continue
            sim = self._combined_similarity(text, old_text)
            if sim > best_sim:
                best_sim = sim
                best = dict(row)
                best["similarity"] = sim
        return best if best_sim >= 0.58 else None

    def _combined_similarity(self, left: str, right: str) -> float:
        semantic = self._semantic_similarity(left, right)
        lexical = self._lexical_similarity(left, right)
        return round((semantic * 0.7) + (lexical * 0.3), 4)

    def _semantic_similarity(self, left: str, right: str) -> float:
        model = _load_semantic_model()
        if model is None:
            return self._lexical_similarity(left, right)
        try:
            embeddings = model.encode([left, right], normalize_embeddings=True)
            if len(embeddings) != 2:
                return self._lexical_similarity(left, right)
            return max(0.0, min(1.0, float((embeddings[0] * embeddings[1]).sum())))
        except Exception:
            return self._lexical_similarity(left, right)

    def _lexical_similarity(self, left: str, right: str) -> float:
        left_tokens = set(self._tokenize(left))
        right_tokens = set(self._tokenize(right))
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))

    def _classify_revision(self, original: str, revised: str) -> Dict[str, Any]:
        o = original.lower()
        r = revised.lower()

        import string
        def _normalize(text):
            return " ".join(text.translate(str.maketrans('', '', string.punctuation)).split())

        if _normalize(o) == _normalize(r):
            return {"revision_type": "no_change", "severity": 0.0, "explanation": "No substantive change"}

        oy = self._extract_target_year(o)
        ry = self._extract_target_year(r)
        if oy and ry and ry > oy:
            return {"revision_type": "deadline_extended", "severity": 65.0, "explanation": f"Deadline moved from {oy} to {ry}"}

        on = self._extract_first_number(o)
        rn = self._extract_first_number(r)
        if on is not None and rn is not None and rn < on:
            return {"revision_type": "target_weakened", "severity": 72.0, "explanation": "Numeric ambition reduced"}

        scope_narrowing_patterns = [
            ("all operations", "operated assets"),
            ("all products", "operated assets"),
            ("all operations and products", "operated assets"),
            ("value chain", "operated assets"),
            ("scope 3", "scope 1 and 2"),
        ]
        if any(src in o and dst in r for src, dst in scope_narrowing_patterns):
            return {"revision_type": "scope_narrowed", "severity": 65.0, "explanation": "Claim boundary narrowed"}

        if any(k in r for k in ["intensity", "efficiency"]) and "absolute" in o:
            return {"revision_type": "reframed", "severity": 55.0, "explanation": "Shifted toward intensity framing"}

        if self._extract_first_number(r) and self._extract_first_number(o):
            if self._extract_first_number(r) > self._extract_first_number(o):
                return {"revision_type": "strengthened", "severity": 20.0, "explanation": "Target appears more ambitious"}

        # Semantic-equivalence gate: if the wording is highly similar (just
        # minor phrasing/punctuation/prefix differences like adding the
        # company name), treat as no substantive change rather than reframing.
        sim = self._combined_similarity(original, revised)
        if sim >= 0.85:
            return {"revision_type": "no_change", "severity": 0.0, "explanation": "Minor wording variation — semantically equivalent"}

        return {"revision_type": "reframed", "severity": 40.0, "explanation": "Wording changed with accountability impact"}

    def _extract_target_year(self, text: str) -> Optional[int]:
        for token in self._tokenize(text):
            if token.isdigit() and len(token) == 4:
                year = int(token)
                if 2000 <= year <= 2100:
                    return year
        return None

    def _extract_first_number(self, text: str) -> Optional[float]:
        out = []
        current = ""
        for ch in text:
            if ch.isdigit() or ch == ".":
                current += ch
            elif current:
                out.append(current)
                current = ""
        if current:
            out.append(current)
        for token in out:
            try:
                return float(token)
            except Exception:
                continue
        return None

    def _target_direction(self, text: str) -> str:
        t = text.lower()
        if "reduce" in t or "decrease" in t or "cut" in t:
            return "reduce"
        if "increase" in t or "grow" in t:
            return "increase"
        if "maintain" in t or "keep" in t:
            return "maintain"
        return "achieve"

    def _best_evidence_url(self, sub_claim_id: Any, evidence: List[Dict[str, Any]]) -> Optional[str]:
        sid = str(sub_claim_id or "")
        for item in evidence or []:
            if not isinstance(item, dict):
                continue
            if sid and str(item.get("sub_claim_id") or "") != sid:
                continue
            url = item.get("url")
            if url:
                return str(url)
        return None

    def _tokenize(self, text: str) -> List[str]:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in str(text or ""))
        return [t for t in cleaned.split() if len(t) > 2]
