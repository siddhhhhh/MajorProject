"""
Neo4j-backed company-centric knowledge graph for ESG facts and GraphRAG.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import os
import re

from dotenv import load_dotenv

from core.kg_schema import (
    ALLOWED_RELATIONSHIPS,
    ENTITY_TYPES,
    validate_graph_package,
)
from core.llm_router import get_langchain_chat_model

load_dotenv()

try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None

try:
    from langchain_experimental.graph_transformers import LLMGraphTransformer
except Exception:
    LLMGraphTransformer = None

# Prefer the new langchain_neo4j package for Neo4jGraph (the
# langchain_community version is deprecated as of LangChain 0.3.8 and
# emits a noisy warning on import). Falls back to langchain_community
# if langchain_neo4j is not installed.
try:
    from langchain_neo4j import Neo4jGraph  # type: ignore
except Exception:
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from langchain_community.graphs import Neo4jGraph  # type: ignore
    except Exception:
        Neo4jGraph = None

try:
    from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
    from langchain_core.documents import Document
except Exception:
    GraphDocument = None
    Node = None
    Relationship = None
    Document = None


HIGH_TRUST_SOURCE_TYPES = {
    "Government/Regulatory": 1,
    "Legal/Court Documents": 1,
    "Government/International Data": 1,
    "Tier-1 Financial Media": 1,
    "Compliance/Sanctions Database": 1,
    "NGO": 2,
    "Climate NGO": 2,
    "Academic": 1,
    "Company-Controlled": 3,
}

LLM_KG_SYSTEM_PROMPT = """
You are extracting a forensic ESG knowledge graph for greenwashing analysis.

Follow the schema exactly.

Allowed entity types:
- Organization
- KPI
- Facility
- RegulatoryVerdict
- SustainabilityGoal
- EvidenceSource

Allowed relationships:
- Organization -> HAS_KPI -> KPI
- Organization -> HAS_REGULATORY_VERDICT -> RegulatoryVerdict
- Organization -> HAS_SUSTAINABILITY_GOAL -> SustainabilityGoal
- Organization -> HAS_FACILITY -> Facility
- Facility -> HAS_REGULATORY_VERDICT -> RegulatoryVerdict
- Facility -> HAS_KPI -> KPI
- KPI -> SUPPORTED_BY -> EvidenceSource
- RegulatoryVerdict -> SUPPORTED_BY -> EvidenceSource
- SustainabilityGoal -> SUPPORTED_BY -> EvidenceSource
- Facility -> SUPPORTED_BY -> EvidenceSource

Prioritize extracting:
- KPI observations
- Regulatory verdicts
- Sustainability goals
- Facility or subsidiary entities when a subsidiary/facility is the subject of a fine, spill, or operational KPI

Mandatory properties for KPI and SustainabilityGoal:
- value
- unit
- year
- source_tier

If a property is not explicit, infer conservatively from context and keep the value grounded in the text.
Use source_tier:
- 1 for regulator, court, government, or tier-1 media
- 2 for NGO or specialist external source
- 3 for company-controlled disclosures or weakly verified text
"""


def _slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip())
    return text.strip("_") or "unknown"


def _normalize_company_anchor(company: str, ticker: str = "") -> str:
    if ticker:
        return f"ticker::{ticker.strip().upper()}"
    return f"name::{_slugify(company).lower()}"


def _safe_year(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    if isinstance(value, int) and 1900 <= value <= 2100:
        return value
    match = re.search(r"(19|20)\d{2}", str(value))
    if not match:
        return default
    year = int(match.group(0))
    return year if 1900 <= year <= 2100 else default


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _source_tier(source_type: str) -> int:
    return HIGH_TRUST_SOURCE_TYPES.get(str(source_type or "").strip(), 3)


def _metric_name_from_text(text: str) -> str:
    low = str(text or "").lower()
    if "scope 1" in low:
        return "Scope1_Emissions"
    if "scope 2" in low:
        return "Scope2_Emissions"
    if "scope 3" in low:
        return "Scope3_Emissions"
    if "ghg intensity" in low or "carbon intensity" in low:
        return "GHG_Intensity"
    if "water" in low:
        return "Water_Use"
    if "waste" in low:
        return "Waste"
    if "renewable" in low:
        return "Renewable_Energy"
    if "fine" in low or "penalty" in low:
        return "Regulatory_Fine"
    if "emission" in low or "carbon" in low:
        return "Carbon_Emissions"
    return "ESG_KPI"


def _extract_goal_value_and_unit(claim_text: str) -> Tuple[float, str]:
    low = str(claim_text or "").lower()
    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", low)
    if percent_match:
        return float(percent_match.group(1)), "%"
    if "net zero" in low or "net-zero" in low:
        return 0.0, "net_zero_target"
    if "carbon negative" in low:
        return -1.0, "carbon_negative_target"
    if "zero waste" in low:
        return 0.0, "zero_waste_target"
    return 1.0, "qualitative_target"


def _extract_goal_name(claim_text: str) -> str:
    low = str(claim_text or "").lower()
    if "net zero" in low or "net-zero" in low:
        return "Net_Zero_Goal"
    if "carbon negative" in low:
        return "Carbon_Negative_Goal"
    if "water positive" in low:
        return "Water_Positive_Goal"
    if "zero waste" in low:
        return "Zero_Waste_Goal"
    if "renewable" in low:
        return "Renewable_Energy_Goal"
    return "Sustainability_Goal"


def _pick_goal_year(claim_text: str, default_year: int | None = None) -> int:
    return _safe_year(claim_text, default=default_year or datetime.now(timezone.utc).year)


def _extract_possible_facility(text: str, company: str, year: int | None = None) -> Dict[str, Any] | None:
    content = str(text or "")
    lower = content.lower()
    if not any(token in lower for token in ["subsidiary", "facility", "plant", "refinery", "nigeria", "site"]):
        return None

    match = re.search(r"([A-Z][A-Za-z0-9&,\-\s]{2,40}?(?:subsidiary|facility|plant|refinery|terminal|operations))", content)
    if match:
        name = match.group(1).strip()
    elif "nigeria" in lower:
        name = f"{company} Nigeria Subsidiary"
    else:
        name = f"{company} Facility"

    node_key = f"{_slugify(company).lower()}::facility::{_slugify(name).lower()}::{year or 'undated'}"
    return {
        "label": "Facility",
        "node_key": node_key,
        "properties": {
            "name": name,
            "year": year or datetime.now(timezone.utc).year,
            "anchor_company": company,
            "facility_type": "subsidiary" if "subsidiary" in name.lower() else "facility",
        },
    }


def _extract_evidence_source_nodes(
    anchor_key: str,
    evidence: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    entities: List[Dict[str, Any]] = []
    mapping: Dict[str, str] = {}
    seen: set[str] = set()

    def add_source(source_name: str, url: str, year: Any, source_type: str) -> str:
        key = f"source::{_slugify(url or source_name or 'unknown')}"
        if key in seen:
            return key
        seen.add(key)
        entities.append(
            {
                "label": "EvidenceSource",
                "node_key": key,
                "properties": {
                    "name": str(source_name or "Unknown Source"),
                    "url": str(url or ""),
                    "year": _safe_year(year, default=datetime.now(timezone.utc).year),
                    "source_type": str(source_type or ""),
                    "source_tier": _source_tier(source_type),
                    "anchor_id": anchor_key,
                },
            }
        )
        return key

    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        source_key = add_source(
            ev.get("source_name") or ev.get("source"),
            ev.get("url") or ev.get("link"),
            ev.get("year") or ev.get("date"),
            ev.get("source_type"),
        )
        text_key = str(ev.get("source_id") or ev.get("id") or "")
        if text_key:
            mapping[text_key] = source_key

    for idx, row in enumerate(contradictions, start=1):
        if not isinstance(row, dict):
            continue
        source_key = add_source(
            row.get("source") or row.get("regulatory_body"),
            row.get("source_url") or row.get("url"),
            row.get("year"),
            row.get("source_type") or "Government/Regulatory",
        )
        mapping[f"contradiction::{idx}"] = source_key

    return entities, mapping


def _extract_kpis(anchor_key: str, company: str, state: Dict[str, Any]) -> List[Dict[str, Any]]:
    year_default = datetime.now(timezone.utc).year
    entities: List[Dict[str, Any]] = []
    carbon = state.get("carbon_extraction", {}) if isinstance(state.get("carbon_extraction"), dict) else {}
    emissions = carbon.get("emissions", {}) if isinstance(carbon.get("emissions"), dict) else {}

    metric_specs = [
        ("scope1", "Scope1_Emissions", emissions.get("scope1", {})),
        ("scope2", "Scope2_Emissions", emissions.get("scope2", {})),
        ("scope3", "Scope3_Emissions", emissions.get("scope3", {})),
    ]
    for metric_key, metric_name, payload in metric_specs:
        if not isinstance(payload, dict):
            continue
        raw_value = payload.get("value")
        if raw_value is None and metric_key == "scope3":
            raw_value = payload.get("total")
        value = _safe_float(raw_value)
        if value is None:
            continue
        unit = str(payload.get("unit") or "tCO2e")
        year = _safe_year(payload.get("year"), default=year_default)
        source_type = str(payload.get("source_type") or "Company-Controlled")
        entities.append(
            {
                "label": "KPI",
                "node_key": f"{anchor_key}::kpi::{metric_name.lower()}::{year}",
                "properties": {
                    "name": metric_name,
                    "value": value,
                    "unit": unit,
                    "year": year,
                    "source_tier": _source_tier(source_type),
                    "source_type": source_type,
                    "anchor_id": anchor_key,
                    "company": company,
                },
            }
        )

    report_json = state.get("json_export")
    if isinstance(report_json, str) and report_json.strip().startswith("{"):
        try:
            parsed = json.loads(report_json)
        except Exception:
            parsed = {}
        pillar_factors = (parsed.get("pillarfactors") or parsed.get("pillar_factors", {})) if isinstance(parsed, dict) else {}
        env = pillar_factors.get("environmental", {}) if isinstance(pillar_factors, dict) else {}
        sub_indicators = env.get("sub_indicators", []) if isinstance(env, dict) else []
        for idx, item in enumerate(sub_indicators, start=1):
            if not isinstance(item, dict):
                continue
            raw_value = item.get("raw_value")
            value = None
            if isinstance(raw_value, str):
                match = re.search(r"(-?\d[\d,\.]*)", raw_value)
                if match:
                    value = _safe_float(match.group(1))
            elif isinstance(raw_value, (int, float)):
                value = float(raw_value)
            if value is None:
                continue
            metric_name = _metric_name_from_text(item.get("name") or raw_value)
            year = _safe_year(item.get("data_year"), default=year_default)
            node_key = f"{anchor_key}::kpi::{metric_name.lower()}::{year}::report::{idx}"
            entities.append(
                {
                    "label": "KPI",
                    "node_key": node_key,
                    "properties": {
                        "name": metric_name,
                        "value": value,
                        "unit": str(item.get("unit") or ""),
                        "year": year,
                        "source_tier": 1 if bool(item.get("verified")) else 2,
                        "source_type": str(item.get("data_source") or "Report"),
                        "source_url": str(item.get("source_url") or ""),
                        "anchor_id": anchor_key,
                        "company": company,
                    },
                }
            )
    return entities


def _extract_goals(anchor_key: str, company: str, claim_text: str, state: Dict[str, Any]) -> List[Dict[str, Any]]:
    year_default = datetime.now(timezone.utc).year
    entities: List[Dict[str, Any]] = []
    value, unit = _extract_goal_value_and_unit(claim_text)
    year = _pick_goal_year(claim_text, default_year=year_default)
    entities.append(
        {
            "label": "SustainabilityGoal",
            "node_key": f"{anchor_key}::goal::{_slugify(_extract_goal_name(claim_text)).lower()}::{year}",
            "properties": {
                "name": _extract_goal_name(claim_text),
                "value": value,
                "unit": unit,
                "year": year,
                "source_tier": 1,
                "source_type": "Claim",
                "claim_text": claim_text,
                "anchor_id": anchor_key,
                "company": company,
            },
        }
    )

    mismatch = state.get("esg_mismatch_analysis", {}) if isinstance(state.get("esg_mismatch_analysis"), dict) else {}
    promises = mismatch.get("promises", [])
    if isinstance(promises, list):
        for idx, promise in enumerate(promises, start=1):
            if not isinstance(promise, dict):
                continue
            p_value = _safe_float(promise.get("target"))
            if p_value is None:
                p_value = 0.0 if "net zero" in str(promise.get("metric", "")).lower() else 1.0
            p_year = _safe_year(promise.get("deadline"), default=year_default)
            p_unit = str(promise.get("unit") or "qualitative_target")
            p_name = str(promise.get("metric") or f"Sustainability_Goal_{idx}")
            entities.append(
                {
                    "label": "SustainabilityGoal",
                    "node_key": f"{anchor_key}::goal::{_slugify(p_name).lower()}::{p_year}::{idx}",
                    "properties": {
                        "name": p_name,
                        "value": p_value,
                        "unit": p_unit,
                        "year": p_year,
                        "source_tier": 1,
                        "source_type": str(promise.get("source") or "Promise Extraction"),
                        "claim_text": str(promise.get("supporting_quote") or promise.get("source") or ""),
                        "anchor_id": anchor_key,
                        "company": company,
                    },
                }
            )
    return entities


def _extract_regulatory_verdicts(
    anchor_key: str,
    company: str,
    contradictions: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    year_default = datetime.now(timezone.utc).year
    verdicts: List[Dict[str, Any]] = []
    facilities: List[Dict[str, Any]] = []
    verdict_to_facility: Dict[str, str] = {}
    seen_facilities: set[str] = set()

    for idx, row in enumerate(contradictions, start=1):
        if not isinstance(row, dict):
            continue
        text = str(row.get("contradiction_text") or row.get("description") or row.get("reasoning") or "").strip()
        if not text:
            continue
        verdict_year = _safe_year(row.get("year"), default=year_default)
        severity = str(row.get("severity") or row.get("risk_level") or "unknown")
        legal_obligation = "mandatory" if any(tok in text.lower() for tok in ["must", "required", "legally binding"]) else "adverse"
        verdict_key = f"{anchor_key}::verdict::{verdict_year}::{idx}"
        verdicts.append(
            {
                "label": "RegulatoryVerdict",
                "node_key": verdict_key,
                "properties": {
                    "name": str(row.get("source") or row.get("regulatory_body") or f"Verdict {idx}"),
                    "summary": text,
                    "year": verdict_year,
                    "severity": severity,
                    "legal_obligation": legal_obligation,
                    "source_tier": _source_tier(row.get("source_type") or "Government/Regulatory"),
                    "source_url": str(row.get("source_url") or row.get("url") or ""),
                    "anchor_id": anchor_key,
                    "company": company,
                },
            }
        )
        facility = _extract_possible_facility(text, company, year=verdict_year)
        if facility and facility["node_key"] not in seen_facilities:
            seen_facilities.add(facility["node_key"])
            facilities.append(facility)
            verdict_to_facility[verdict_key] = facility["node_key"]
        elif facility:
            verdict_to_facility[verdict_key] = facility["node_key"]

    return verdicts, facilities, verdict_to_facility


def _build_transformer() -> Any | None:
    if LLMGraphTransformer is None or Document is None:
        return None
    chat_model = get_langchain_chat_model(
        agent_name="kg_extraction",
        system_prompt=LLM_KG_SYSTEM_PROMPT,
        json_mode=True,
    )
    return LLMGraphTransformer(
        llm=chat_model,
        allowed_nodes=sorted(ENTITY_TYPES),
        allowed_relationships=sorted(ALLOWED_RELATIONSHIPS),
        strict_mode=True,
        node_properties=["value", "unit", "year", "source_tier", "name", "summary", "source_url"],
        relationship_properties=False,
        additional_instructions=(
            "All extracted nodes must remain grounded in the source text. "
            "Prefer Facility nodes for subsidiaries and operational sites. "
            "If the organization is implied, attach the extracted nodes to the persistent company anchor."
        ),
    )


def build_company_kg_package(state: Dict[str, Any]) -> Dict[str, Any]:
    company = str(state.get("company") or "").strip()
    if not company:
        raise ValueError("State missing company.")
    ticker = ""
    financial_context = state.get("financial_context", {})
    if isinstance(financial_context, dict):
        ticker = str(financial_context.get("ticker") or "").strip()

    claim_text = str(state.get("claim") or "").strip()
    industry = str(state.get("industry") or "").strip()
    anchor_key = _normalize_company_anchor(company, ticker=ticker)
    contradictions = []
    outputs = state.get("agent_outputs", [])
    if isinstance(outputs, list):
        for item in reversed(outputs):
            if isinstance(item, dict) and item.get("agent") == "contradiction_analysis":
                payload = item.get("output", {})
                if isinstance(payload, list):
                    contradictions = payload
                elif isinstance(payload, dict):
                    contradictions = (
                        payload.get("contradictions")
                        or payload.get("contradiction_list")
                        or payload.get("specific_contradictions")
                        or []
                    )
                break

    evidence = state.get("evidence", []) if isinstance(state.get("evidence"), list) else []
    source_entities, source_lookup = _extract_evidence_source_nodes(anchor_key, evidence, contradictions if isinstance(contradictions, list) else [])
    kpis = _extract_kpis(anchor_key, company, state)
    goals = _extract_goals(anchor_key, company, claim_text, state)
    verdicts, facilities, verdict_to_facility = _extract_regulatory_verdicts(anchor_key, company, contradictions if isinstance(contradictions, list) else [])

    organization = {
        "label": "Organization",
        "node_key": anchor_key,
        "properties": {
            "anchor_id": anchor_key,
            "name": company,
            "ticker": ticker,
            "industry": industry,
            "last_ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    entities = source_entities + kpis + goals + verdicts + facilities
    relationships: List[Dict[str, Any]] = []

    for node in kpis:
        relationships.append({"source_key": anchor_key, "type": "HAS_KPI", "target_key": node["node_key"]})
    for node in goals:
        relationships.append({"source_key": anchor_key, "type": "HAS_SUSTAINABILITY_GOAL", "target_key": node["node_key"]})
    for node in facilities:
        relationships.append({"source_key": anchor_key, "type": "HAS_FACILITY", "target_key": node["node_key"]})
    for node in verdicts:
        facility_key = verdict_to_facility.get(node["node_key"])
        if facility_key:
            relationships.append({"source_key": facility_key, "type": "HAS_REGULATORY_VERDICT", "target_key": node["node_key"]})
        else:
            relationships.append({"source_key": anchor_key, "type": "HAS_REGULATORY_VERDICT", "target_key": node["node_key"]})

    primary_source_key = next(iter(source_lookup.values()), "")
    if primary_source_key:
        for node in kpis + goals + facilities:
            relationships.append({"source_key": node["node_key"], "type": "SUPPORTED_BY", "target_key": primary_source_key})

    contradiction_source_keys = [source_lookup.get(f"contradiction::{idx}") for idx, _ in enumerate(verdicts, start=1)]
    for node, source_key in zip(verdicts, contradiction_source_keys):
        if source_key:
            relationships.append({"source_key": node["node_key"], "type": "SUPPORTED_BY", "target_key": source_key})

    package = validate_graph_package(organization=organization, entities=entities, relationships=relationships)
    package["summary"] = {
        "organization_anchor": anchor_key,
        "entity_count": len(package["entities"]) + 1,
        "relationship_count": len(package["relationships"]),
        "kpi_count": len(kpis),
        "goal_count": len(goals),
        "regulatory_verdict_count": len(verdicts),
        "facility_count": len(facilities),
        "evidence_source_count": len(source_entities),
        "llm_graph_transformer_available": bool(LLMGraphTransformer is not None),
    }
    return package


class CompanyKnowledgeGraph:
    def __init__(self) -> None:
        self.enabled = os.getenv("KG_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
        self.uri = os.getenv("NEO4J_URI", "").strip()
        self.driver_uri = self._normalize_driver_uri(self.uri)
        self.username = os.getenv("NEO4J_USERNAME", "").strip()
        self.password = os.getenv("NEO4J_PASSWORD", "").strip()
        self.database = os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j"
        self.use_llm_graph_transformer = os.getenv("KG_USE_LLM_GRAPH_TRANSFORMER", "false").strip().lower() in {"1", "true", "yes"}
        self._transformer = None

    def _normalize_driver_uri(self, uri: str) -> str:
        """Use direct bolt for local single-instance Neo4j to avoid routing issues."""
        cleaned = str(uri or "").strip()
        if cleaned.startswith("neo4j://127.0.0.1") or cleaned.startswith("neo4j://localhost"):
            return "bolt://" + cleaned[len("neo4j://"):]
        return cleaned

    def is_configured(self) -> bool:
        return self.enabled and bool(self.uri and self.username and self.password and GraphDatabase is not None)

    def _get_driver(self):
        if not self.is_configured():
            return None
        return GraphDatabase.driver(self.driver_uri or self.uri, auth=(self.username, self.password))

    def _get_graph(self):
        if not self.is_configured() or Neo4jGraph is None:
            return None
        # Suppress the LangChain 0.3.8 deprecation warning fired by the
        # community Neo4jGraph at construction. We're not migrating to
        # langchain_neo4j yet; KG/Fact-Graph logic is independent of
        # which Neo4jGraph wrapper is used.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return Neo4jGraph(
                url=self.driver_uri or self.uri,
                username=self.username,
                password=self.password,
                database=self.database,
                refresh_schema=False,
            )

    def _get_transformer(self):
        if self._transformer is None:
            self._transformer = _build_transformer()
        return self._transformer

    def _ensure_constraints(self, session) -> None:
        session.run("CREATE CONSTRAINT org_anchor IF NOT EXISTS FOR (n:Organization) REQUIRE n.anchor_id IS UNIQUE")
        session.run("CREATE CONSTRAINT kpi_node_key IF NOT EXISTS FOR (n:KPI) REQUIRE n.node_key IS UNIQUE")
        session.run("CREATE CONSTRAINT goal_node_key IF NOT EXISTS FOR (n:SustainabilityGoal) REQUIRE n.node_key IS UNIQUE")
        session.run("CREATE CONSTRAINT verdict_node_key IF NOT EXISTS FOR (n:RegulatoryVerdict) REQUIRE n.node_key IS UNIQUE")
        session.run("CREATE CONSTRAINT source_node_key IF NOT EXISTS FOR (n:EvidenceSource) REQUIRE n.node_key IS UNIQUE")
        session.run("CREATE CONSTRAINT facility_node_key IF NOT EXISTS FOR (n:Facility) REQUIRE n.node_key IS UNIQUE")

    def _merge_entity(self, session, label: str, node_key: str, properties: Dict[str, Any]) -> None:
        id_field = "anchor_id" if label == "Organization" else "node_key"
        cypher = f"""
        MERGE (n:{label} {{{id_field}: $identity}})
        SET n += $properties
        """
        identity = node_key if label != "Organization" else properties.get("anchor_id")
        session.run(cypher, identity=identity, properties=properties)

    def _merge_relationship(self, session, source_key: str, source_label: str, rel_type: str, target_key: str, target_label: str) -> None:
        source_field = "anchor_id" if source_label == "Organization" else "node_key"
        target_field = "anchor_id" if target_label == "Organization" else "node_key"
        cypher = f"""
        MATCH (a:{source_label} {{{source_field}: $source_key}})
        MATCH (b:{target_label} {{{target_field}: $target_key}})
        MERGE (a)-[r:{rel_type}]->(b)
        """
        session.run(cypher, source_key=source_key, target_key=target_key)

    def _persist_local_payload(self, package: Dict[str, Any], company: str) -> str:
        out_dir = Path("reports") / "company_kg"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{_slugify(company)}_company_kg_payload.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(package, f, indent=2, ensure_ascii=False)
        # Also append KPIs from this run to a per-company JSONL history so
        # downstream agents can query year-over-year drift across runs.
        # The main payload above OVERWRITES each run, which loses history;
        # this JSONL is APPEND-ONLY for cross-run intelligence.
        try:
            self._append_kpi_history(package, company, out_dir)
        except Exception as exc:
            print(f"⚠️  KPI history append failed: {exc}")
        return str(path)

    def _append_kpi_history(self, package: Dict[str, Any], company: str, out_dir: Path) -> None:
        """Append this run's KPI snapshots to a per-company JSONL history file."""
        kpi_entries = [
            e for e in (package.get("entities") or [])
            if isinstance(e, dict) and e.get("label") == "KPI"
        ]
        if not kpi_entries:
            return
        history_path = out_dir / f"{_slugify(company)}_kpi_history.jsonl"
        run_ts = datetime.now(timezone.utc).isoformat()
        with history_path.open("a", encoding="utf-8") as f:
            for entry in kpi_entries:
                props = entry.get("properties") or {}
                row = {
                    "run_ts": run_ts,
                    "company": company,
                    "node_key": entry.get("node_key"),
                    "metric_name": props.get("name"),
                    "value": props.get("value"),
                    "unit": props.get("unit"),
                    "year": props.get("year"),
                    "source_tier": props.get("source_tier"),
                    "source_type": props.get("source_type"),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _extract_graph_texts(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        texts: List[Dict[str, Any]] = []
        claim = str(state.get("claim") or "").strip()
        company = str(state.get("company") or "").strip()
        if claim:
            texts.append(
                {
                    "text": claim,
                    "metadata": {
                        "kind": "claim",
                        "company": company,
                        "year": datetime.now(timezone.utc).year,
                        "source_tier": 1,
                    },
                }
            )

        for ev in state.get("evidence", []) if isinstance(state.get("evidence"), list) else []:
            if not isinstance(ev, dict):
                continue
            text = str(ev.get("full_text") or ev.get("relevant_text") or ev.get("snippet") or "").strip()
            if not text:
                continue
            texts.append(
                {
                    "text": text[:4000],
                    "metadata": {
                        "kind": "evidence",
                        "company": company,
                        "source_name": ev.get("source_name") or ev.get("source"),
                        "source_url": ev.get("url") or ev.get("link"),
                        "year": _safe_year(ev.get("year") or ev.get("date"), default=datetime.now(timezone.utc).year),
                        "source_tier": _source_tier(ev.get("source_type")),
                    },
                }
            )

        outputs = state.get("agent_outputs", [])
        contradictions: List[Dict[str, Any]] = []
        if isinstance(outputs, list):
            for item in reversed(outputs):
                if isinstance(item, dict) and item.get("agent") == "contradiction_analysis":
                    payload = item.get("output", {})
                    if isinstance(payload, dict):
                        contradictions = (
                            payload.get("contradictions")
                            or payload.get("contradiction_list")
                            or payload.get("specific_contradictions")
                            or []
                        )
                    break
        for row in contradictions[:15]:
            if not isinstance(row, dict):
                continue
            text = str(row.get("contradiction_text") or row.get("description") or row.get("reasoning") or "").strip()
            if not text:
                continue
            texts.append(
                {
                    "text": text,
                    "metadata": {
                        "kind": "contradiction",
                        "company": company,
                        "source_name": row.get("source") or row.get("regulatory_body"),
                        "source_url": row.get("source_url") or row.get("url"),
                        "year": _safe_year(row.get("year"), default=datetime.now(timezone.utc).year),
                        "source_tier": _source_tier(row.get("source_type") or "Government/Regulatory"),
                    },
                }
            )
        return texts

    def _ensure_measure_defaults(self, node_type: str, props: Dict[str, Any], metadata: Dict[str, Any], text: str) -> Dict[str, Any]:
        props = dict(props or {})
        if "year" not in props or props.get("year") in (None, ""):
            props["year"] = _safe_year(metadata.get("year"), default=datetime.now(timezone.utc).year)
        if "source_tier" not in props or props.get("source_tier") in (None, ""):
            props["source_tier"] = int(metadata.get("source_tier") or 3)
        if node_type in {"KPI", "SustainabilityGoal"}:
            if "value" not in props or props.get("value") in (None, ""):
                match = re.search(r"(-?\d+(?:\.\d+)?)", text)
                props["value"] = float(match.group(1)) if match else (0.0 if "zero" in text.lower() else 1.0)
            else:
                props["value"] = float(props["value"])
            if "unit" not in props or not props.get("unit"):
                if "%" in text:
                    props["unit"] = "%"
                elif "tco2" in text.lower():
                    props["unit"] = "tCO2e"
                elif "million" in text.lower() and "dollar" in text.lower():
                    props["unit"] = "USD_million"
                elif "usd" in text.lower() or "$" in text:
                    props["unit"] = "USD"
                else:
                    props["unit"] = "qualitative_target" if node_type == "SustainabilityGoal" else "unitless"
        return props

    def _normalize_graph_documents(
        self,
        graph_documents: List[Any],
        company_node: Dict[str, Any],
        metadata: Dict[str, Any],
        text: str,
    ) -> List[Any]:
        if GraphDocument is None or Node is None or Relationship is None:
            return []

        company_anchor = company_node["properties"]["anchor_id"]
        company_name = company_node["properties"]["name"]
        normalized_docs: List[Any] = []

        for doc in graph_documents:
            raw_nodes = getattr(doc, "nodes", []) or []
            raw_relationships = getattr(doc, "relationships", []) or []

            nodes_by_id: Dict[str, Any] = {}
            relationships: List[Any] = []

            org_node = Node(
                id=company_anchor,
                type="Organization",
                properties=dict(company_node["properties"]),
            )
            nodes_by_id[company_anchor] = org_node

            for raw_node in raw_nodes:
                node_type = getattr(raw_node, "type", "") or "EvidenceSource"
                if node_type == "KPIObservation":
                    node_type = "KPI"
                if node_type not in ENTITY_TYPES:
                    continue
                raw_id = str(getattr(raw_node, "id", "") or "")
                props = dict(getattr(raw_node, "properties", {}) or {})
                if node_type == "Organization":
                    nodes_by_id[company_anchor] = org_node
                    continue
                if "name" not in props or not props.get("name"):
                    props["name"] = raw_id or node_type
                if node_type == "EvidenceSource":
                    props.setdefault("source_tier", int(metadata.get("source_tier") or 3))
                    props.setdefault("url", str(metadata.get("source_url") or ""))
                    props.setdefault("year", _safe_year(metadata.get("year"), default=datetime.now(timezone.utc).year))
                props = self._ensure_measure_defaults(node_type, props, metadata, text)
                if "summary" not in props and node_type == "RegulatoryVerdict":
                    props["summary"] = text[:500]
                node_key = f"{company_anchor}::{node_type.lower()}::{_slugify(raw_id or props.get('name') or node_type).lower()}"
                props.setdefault("anchor_id", company_anchor)
                props.setdefault("company", company_name)
                nodes_by_id[node_key] = Node(id=node_key, type=node_type, properties=props)

            if len(nodes_by_id) == 1:
                derived_type = "Facility" if "subsidiary" in text.lower() or "facility" in text.lower() else (
                    "RegulatoryVerdict" if any(tok in text.lower() for tok in ["fine", "penalty", "court", "ruled"]) else (
                        "SustainabilityGoal" if any(tok in text.lower() for tok in ["target", "goal", "net-zero", "net zero", "carbon negative"]) else "KPI"
                    )
                )
                props = {
                    "name": _metric_name_from_text(text) if derived_type == "KPI" else _extract_goal_name(text),
                }
                props = self._ensure_measure_defaults(derived_type, props, metadata, text)
                if derived_type == "RegulatoryVerdict":
                    props["summary"] = text[:500]
                    props["severity"] = "medium"
                    props["legal_obligation"] = "adverse"
                derived_key = f"{company_anchor}::{derived_type.lower()}::{_slugify(props.get('name') or text[:40]).lower()}"
                props.setdefault("anchor_id", company_anchor)
                props.setdefault("company", company_name)
                nodes_by_id[derived_key] = Node(id=derived_key, type=derived_type, properties=props)

            for raw_rel in raw_relationships:
                rel_type = str(getattr(raw_rel, "type", "") or "").strip()
                if not rel_type:
                    continue
                source = getattr(raw_rel, "source", None)
                target = getattr(raw_rel, "target", None)
                source_id = company_anchor if getattr(source, "type", "") == "Organization" else f"{company_anchor}::{getattr(source, 'type', '').lower()}::{_slugify(getattr(source, 'id', '') or getattr(source, 'properties', {}).get('name') or '')}"
                target_id = company_anchor if getattr(target, "type", "") == "Organization" else f"{company_anchor}::{getattr(target, 'type', '').lower()}::{_slugify(getattr(target, 'id', '') or getattr(target, 'properties', {}).get('name') or '')}"
                if source_id not in nodes_by_id or target_id not in nodes_by_id:
                    continue
                triple = (nodes_by_id[source_id].type, rel_type, nodes_by_id[target_id].type)
                if triple not in ALLOWED_RELATIONSHIPS:
                    continue
                relationships.append(
                    Relationship(
                        source=nodes_by_id[source_id],
                        target=nodes_by_id[target_id],
                        type=rel_type,
                        properties={},
                    )
                )

            for node_id, node in list(nodes_by_id.items()):
                if node.type == "Organization":
                    continue
                if node.type == "Facility":
                    rel_type = "HAS_FACILITY"
                elif node.type == "KPI":
                    rel_type = "HAS_KPI"
                elif node.type == "RegulatoryVerdict":
                    rel_type = "HAS_REGULATORY_VERDICT"
                elif node.type == "SustainabilityGoal":
                    rel_type = "HAS_SUSTAINABILITY_GOAL"
                else:
                    continue
                triple = ("Organization", rel_type, node.type)
                if triple in ALLOWED_RELATIONSHIPS and not any(r.source.id == company_anchor and r.target.id == node_id and r.type == rel_type for r in relationships):
                    relationships.append(
                        Relationship(source=org_node, target=node, type=rel_type, properties={})
                    )

            source_nodes = [n for n in nodes_by_id.values() if n.type == "EvidenceSource"]
            for source_node in source_nodes:
                continue
            if metadata.get("source_url") or metadata.get("source_name"):
                source_node = Node(
                    id=f"{company_anchor}::evidencesource::{_slugify(metadata.get('source_url') or metadata.get('source_name') or 'source').lower()}",
                    type="EvidenceSource",
                    properties={
                        "name": str(metadata.get("source_name") or "Knowledge Graph Source"),
                        "url": str(metadata.get("source_url") or ""),
                        "year": _safe_year(metadata.get("year"), default=datetime.now(timezone.utc).year),
                        "source_type": str(metadata.get("kind") or "graph_source"),
                        "source_tier": int(metadata.get("source_tier") or 3),
                        "anchor_id": company_anchor,
                    },
                )
                nodes_by_id[source_node.id] = source_node
                for node in nodes_by_id.values():
                    if node.type in {"KPI", "RegulatoryVerdict", "SustainabilityGoal", "Facility"}:
                        triple = (node.type, "SUPPORTED_BY", "EvidenceSource")
                        if triple in ALLOWED_RELATIONSHIPS:
                            relationships.append(
                                Relationship(source=node, target=source_node, type="SUPPORTED_BY", properties={})
                            )

            normalized_docs.append(
                GraphDocument(
                    nodes=list(nodes_by_id.values()),
                    relationships=relationships,
                    source=Document(page_content=text, metadata=metadata),
                )
            )

        return normalized_docs

    def process_text_to_kg(self, text: str, company_node: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> List[Any]:
        metadata = metadata or {}
        if not text or not self.use_llm_graph_transformer:
            return []
        transformer = self._get_transformer()
        if transformer is None or Document is None:
            return []
        graph_documents = transformer.convert_to_graph_documents(
            [Document(page_content=text, metadata=metadata)]
        )
        return self._normalize_graph_documents(graph_documents, company_node, metadata, text)

    def run_cypher(self, cypher: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return []
        try:
            graph = self._get_graph()
            if graph is None:
                return []
            rows = graph.query(cypher, params=params or {})
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    def get_reasoning_paths(self, company: str, ticker: str = "") -> List[str]:
        anchor = _normalize_company_anchor(company, ticker=ticker)
        if self.is_configured():
            rows = self.run_cypher(
                """
                MATCH p=(o:Organization {anchor_id: $anchor_id})-[*1..2]->(n)
                RETURN [node IN nodes(p) | coalesce(node.name, node.summary, node.anchor_id, node.node_key)] AS node_names,
                       [rel IN relationships(p) | type(rel)] AS rel_types
                LIMIT 10
                """,
                {"anchor_id": anchor},
            )
            paths = []
            for row in rows:
                node_names = row.get("node_names", [])
                rel_types = row.get("rel_types", [])
                if not isinstance(node_names, list) or not isinstance(rel_types, list):
                    continue
                segments: List[str] = []
                for idx, name in enumerate(node_names):
                    segments.append(str(name))
                    if idx < len(rel_types):
                        segments.append(f"-[{rel_types[idx]}]->")
                if segments:
                    paths.append(" ".join(segments))
            return paths

        payload_path = Path("reports") / "company_kg" / f"{_slugify(company)}_company_kg_payload.json"
        if not payload_path.exists():
            return []
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        entities = {payload["organization"]["node_key"]: payload["organization"]["properties"].get("name", company)}
        for entity in payload.get("entities", []):
            entities[entity["node_key"]] = entity.get("properties", {}).get("name") or entity.get("properties", {}).get("summary") or entity["node_key"]
        paths = []
        for rel in payload.get("relationships", [])[:10]:
            source = entities.get(rel.get("source_key"), rel.get("source_key"))
            target = entities.get(rel.get("target_key"), rel.get("target_key"))
            paths.append(f"{source} -[{rel.get('type')}]-> {target}")
        return paths

    def hybrid_retrieve(self, company: str, claim_text: str, ticker: str = "") -> Dict[str, Any]:
        anchor = _normalize_company_anchor(company, ticker=ticker)
        evidence_rows: List[Dict[str, Any]] = []
        reasoning_paths = self.get_reasoning_paths(company, ticker=ticker)

        if self.is_configured():
            rows = self.run_cypher(
                """
                MATCH (o:Organization {anchor_id: $anchor_id})-[r]->(n)
                OPTIONAL MATCH (n)-[:SUPPORTED_BY]->(s:EvidenceSource)
                RETURN type(r) AS relationship_type,
                       labels(n) AS node_labels,
                       coalesce(n.name, n.summary, n.node_key) AS node_name,
                       n.summary AS summary,
                       n.value AS value,
                       n.unit AS unit,
                       n.year AS year,
                       coalesce(s.name, '') AS source_name,
                       coalesce(s.url, '') AS source_url,
                       coalesce(s.source_tier, n.source_tier, 3) AS source_tier
                LIMIT 20
                """,
                {"anchor_id": anchor},
            )
            for row in rows:
                evidence_rows.append(
                    {
                        "source_id": f"kg_{len(evidence_rows)+1:03d}",
                        "source_name": row.get("source_name") or "Knowledge Graph",
                        "source_type": "Knowledge Graph",
                        "url": row.get("source_url", ""),
                        "title": row.get("node_name", ""),
                        "snippet": row.get("summary") or row.get("node_name", ""),
                        "relevant_text": row.get("summary") or row.get("node_name", ""),
                        "relationship_to_claim": "Contradicts" if row.get("relationship_type") == "HAS_REGULATORY_VERDICT" else "Supports",
                        "data_source_api": "Neo4j GraphRAG",
                        "year": row.get("year"),
                        "graph_path": next((p for p in reasoning_paths if str(row.get("node_name", "")) in p), ""),
                    }
                )
        else:
            payload_path = Path("reports") / "company_kg" / f"{_slugify(company)}_company_kg_payload.json"
            if payload_path.exists():
                try:
                    payload = json.loads(payload_path.read_text(encoding="utf-8"))
                except Exception:
                    payload = {}
                entities = payload.get("entities", [])
                for entity in entities[:20]:
                    props = entity.get("properties", {}) if isinstance(entity, dict) else {}
                    evidence_rows.append(
                        {
                            "source_id": f"kg_{len(evidence_rows)+1:03d}",
                            "source_name": "Company KG Payload",
                            "source_type": "Knowledge Graph",
                            "url": props.get("source_url", ""),
                            "title": props.get("name") or entity.get("label"),
                            "snippet": props.get("summary") or props.get("claim_text") or props.get("name", ""),
                            "relevant_text": props.get("summary") or props.get("claim_text") or props.get("name", ""),
                            "relationship_to_claim": "Contradicts" if entity.get("label") == "RegulatoryVerdict" else "Supports",
                            "data_source_api": "Local KG Payload",
                            "year": props.get("year"),
                            "graph_path": next((p for p in reasoning_paths if str(props.get("name", "")) in p), ""),
                        }
                    )

        return {
            "anchor_id": anchor,
            "graph_evidence": evidence_rows,
            "reasoning_paths": reasoning_paths,
            "abstain_recommended": len(evidence_rows) == 0,
            "abstention_reason": "ABSTAIN: Insufficient verifiable evidence in Knowledge Graph" if len(evidence_rows) == 0 else None,
        }

    def ingest_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        package = build_company_kg_package(state)
        company = str(state.get("company") or "Unknown")
        payload_path = self._persist_local_payload(package, company)

        status = {
            "enabled": self.enabled,
            "configured": self.is_configured(),
            "neo4j_available": GraphDatabase is not None,
            "llm_graph_transformer_requested": self.use_llm_graph_transformer,
            "llm_graph_transformer_available": bool(LLMGraphTransformer is not None),
            "organization_anchor": package.get("summary", {}).get("organization_anchor"),
            "entity_count": package.get("summary", {}).get("entity_count"),
            "relationship_count": package.get("summary", {}).get("relationship_count"),
            "payload_path": payload_path,
            "query_examples": {
                "company_dump": f"MATCH (o:Organization {{anchor_id: '{package['organization']['properties']['anchor_id']}'}})-->(g) RETURN o, g",
                "shell_verification": "MATCH (o:Organization {name: 'Shell'})-->(g) RETURN g",
                "microsoft_trend": "MATCH (o:Organization {name: 'Microsoft'})-[:HAS_KPI]->(k:KPI {name: 'GHG_Intensity'}) RETURN k.year, k.value ORDER BY k.year",
            },
            "reasoning_paths": self.get_reasoning_paths(company),
        }

        if not self.is_configured():
            status["status"] = "local_payload_only"
            return status

        driver = self._get_driver()
        if driver is None:
            status["status"] = "driver_unavailable"
            status["neo4j_warning"] = "Neo4j driver could not be created; local payload still written."
            return status

        # Defense in depth: connection-establishment failures should NOT mark
        # the agent FAILED, since the local JSON payload already persisted
        # successfully and downstream consumers (drift queries, KG history
        # section) read from that file. Only TRUE Cypher errors should bubble.
        try:
            driver.verify_connectivity()
        except Exception as conn_exc:
            try:
                driver.close()
            except Exception:
                pass
            status["status"] = "neo4j_unreachable"
            status["neo4j_warning"] = (
                f"Neo4j unreachable ({type(conn_exc).__name__}: {str(conn_exc)[:120]}); "
                "local JSON payload still written and KG history features will work. "
                "To enable Neo4j sync set NEO4J_URI/USERNAME/PASSWORD correctly."
            )
            return status

        try:
            entity_lookup = {package["organization"]["node_key"]: package["organization"]["label"]}
            for entity in package.get("entities", []):
                entity_lookup[entity["node_key"]] = entity["label"]

            with driver.session(database=self.database) as session:
                self._ensure_constraints(session)
                org = package["organization"]
                self._merge_entity(session, org["label"], org["node_key"], org["properties"])
                for entity in package.get("entities", []):
                    props = dict(entity["properties"])
                    props["node_key"] = entity["node_key"]
                    self._merge_entity(session, entity["label"], entity["node_key"], props)
                for rel in package.get("relationships", []):
                    self._merge_relationship(
                        session,
                        rel["source_key"],
                        entity_lookup[rel["source_key"]],
                        rel["type"],
                        rel["target_key"],
                        entity_lookup[rel["target_key"]],
                    )

                graph_docs_added = 0
                if self.use_llm_graph_transformer and Neo4jGraph is not None and GraphDocument is not None:
                    graph = self._get_graph()
                    if graph is not None:
                        company_node = package["organization"]
                        for item in self._extract_graph_texts(state):
                            graph_docs = self.process_text_to_kg(
                                text=item["text"],
                                company_node=company_node,
                                metadata=item.get("metadata", {}),
                            )
                            if graph_docs:
                                graph.add_graph_documents(graph_docs, include_source=False)
                                graph_docs_added += len(graph_docs)
                status["graph_documents_added"] = graph_docs_added
            status["status"] = "ingested_to_neo4j"
            status["reasoning_paths"] = self.get_reasoning_paths(company)
        finally:
            driver.close()

        return status


def get_kpi_history(company: str, metric_name=None, exclude_run_ts=None):
    """Return prior KPI snapshots for a company.

    If metric_name is provided, filter to that metric. Sorted newest-first.
    Pass `exclude_run_ts` to skip the current run's freshly-appended row when
    computing drift.
    """
    history_path = Path("reports") / "company_kg" / f"{_slugify(company)}_kpi_history.jsonl"
    if not history_path.exists():
        return []
    rows = []
    try:
        with history_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if metric_name and row.get("metric_name") != metric_name:
                    continue
                if exclude_run_ts and row.get("run_ts") == exclude_run_ts:
                    continue
                rows.append(row)
    except Exception:
        return []
    rows.sort(key=lambda r: r.get("run_ts") or "", reverse=True)
    return rows


def compute_kpi_drift(company: str, metric_name: str, current_value):
    """Compare a current KPI value against the most recent prior recorded
    value in the per-company KPI history. Returns drift % and direction.

    Direction: 'improved' / 'worsened' / 'stable' / 'no_history'.
    For emissions/waste/fines, lower=improved; for renewable_pct etc.,
    higher=improved (decided via the `lower_is_better` heuristic).
    """
    if current_value is None:
        return {"direction": "no_history", "_note": "current value is None"}
    history = get_kpi_history(company, metric_name=metric_name)
    if not history:
        return {"direction": "no_history", "_note": "no prior runs in KPI history"}
    prior = None
    for row in history:
        if row.get("value") is not None:
            prior = row
            break
    if prior is None:
        return {"direction": "no_history", "_note": "no prior values found"}
    try:
        prior_v = float(prior.get("value"))
    except Exception:
        return {"direction": "no_history", "_note": "prior value not numeric"}
    delta = float(current_value) - prior_v
    delta_pct = (delta / prior_v * 100.0) if prior_v else None
    lower_is_better = any(
        tok in (metric_name or "").lower()
        for tok in ("emissions", "co2", "ghg", "waste", "fines")
    )
    if abs(delta_pct or 0) < 1.0:
        direction = "stable"
    elif lower_is_better:
        direction = "improved" if delta < 0 else "worsened"
    else:
        direction = "improved" if delta > 0 else "worsened"
    return {
        "metric_name": metric_name,
        "current_value": float(current_value),
        "prior_value": prior_v,
        "prior_run_ts": prior.get("run_ts"),
        "prior_year": prior.get("year"),
        "delta_abs": round(delta, 4),
        "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
        "direction": direction,
        "lower_is_better": lower_is_better,
        "history_runs_seen": len(history),
    }
