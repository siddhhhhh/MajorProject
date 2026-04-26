import asyncio
import re
from typing import Any, Dict, List, Optional

from ddgs import DDGS


JURISDICTION_MAP = {
    "oil_and_gas": ["UK", "EU", "Netherlands", "US", "Global"],
    "energy": ["UK", "EU", "Netherlands", "US", "Global"],
    "technology": ["UK", "EU", "US", "California"],
    "banking": ["UK", "EU", "US", "Basel"],
    "automotive": ["EU", "US", "California", "China"],
}


class MultiJurisdictionRegulatoryScanner:
    def __init__(self) -> None:
        self.name = "Parallel Multi-Jurisdiction Regulatory Scanner"
        self.jurisdiction_domains = {
            "UK": ["gov.uk", "fca.org.uk", "find-and-update.company-information.service.gov.uk"],
            "EU": ["eur-lex.europa.eu", "ec.europa.eu", "esma.europa.eu"],
            "Netherlands": ["afm.nl", "rechtspraak.nl", "europa.eu"],
            "US": ["sec.gov", "ftc.gov", "epa.gov"],
            "Global": ["sbti.org", "cdp.net", "gri.org", "wri.org"],
        }

    def detect_jurisdictions(self, industry: str, hq_country: str = "") -> List[str]:
        key = (industry or "").lower().replace(" ", "_")
        base = list(JURISDICTION_MAP.get(key, ["UK", "EU"]))
        if hq_country:
            base.append(hq_country)
        # Preserve order while deduplicating
        seen = set()
        ordered = []
        for item in base:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    def aggregate_results(
        self,
        company: str,
        claim_text: str,
        jurisdictions: List[str],
        base_regulatory: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        sbti_status: str = "unknown",
    ) -> Dict[str, Any]:
        rows = asyncio.run(
            self._aggregate_async(
                company=company,
                claim_text=claim_text,
                jurisdictions=jurisdictions,
                base_regulatory=base_regulatory,
                evidence=evidence,
                sbti_status=sbti_status,
            )
        )

        active_litigation_count = len([r for r in rows if str(r.get("framework", "")).lower().startswith("active enforcement")])

        total_penalty = sum(float(r.get("penalty_score", 0) or 0) for r in rows)
        compliance_score = max(0.0, 100.0 - min(95.0, total_penalty))

        risk_level = "low"
        if compliance_score < 35:
            risk_level = "critical"
        elif compliance_score < 55:
            risk_level = "high"
        elif compliance_score < 75:
            risk_level = "medium"

        highest_risk_jurisdiction = "Global"
        if rows:
            by_j = {}
            for r in rows:
                j = str(r.get("jurisdiction") or "Global")
                by_j[j] = by_j.get(j, 0.0) + float(r.get("penalty_score", 0) or 0)
            highest_risk_jurisdiction = max(by_j, key=by_j.get)

        return {
            "jurisdictions": jurisdictions,
            "jurisdiction_results": rows,
            "active_litigation_count": active_litigation_count,
            "total_compliance_score": round(compliance_score, 1),
            "highest_risk_jurisdiction": highest_risk_jurisdiction,
            "regulatory_risk_level": risk_level,
            "investor_disclosure_risk": "Cross-jurisdiction disclosure gaps may create material misstatement exposure.",
        }

    async def _aggregate_async(
        self,
        company: str,
        claim_text: str,
        jurisdictions: List[str],
        base_regulatory: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        sbti_status: str,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        base_rows = base_regulatory.get("compliance_results", []) if isinstance(base_regulatory, dict) else []
        for row in base_rows:
            if not isinstance(row, dict):
                continue
            framework = str(row.get("regulation_name") or "Framework")
            gaps = row.get("gap_details", []) if isinstance(row.get("gap_details"), list) else []
            status = "compliant" if not gaps else "gap"
            rows.append({
                "jurisdiction": self._infer_framework_jurisdiction(framework, jurisdictions),
                "framework": framework,
                "status": status,
                "specific_violation": gaps[0] if gaps else "",
                "penalty_score": 0 if not gaps else min(30, 8 + len(gaps) * 4),
                "material_misstatement_risk": bool(gaps),
                "evidence_url": None,
                "remediation_required": "Provide framework-specific metric disclosures" if gaps else "-",
            })

        claim_lower = (claim_text or "").lower()
        jurisdiction_tasks = [self._scan_jurisdiction(j, company, claim_text, evidence, sbti_status) for j in jurisdictions or ["Global"]]
        scanned_rows = await asyncio.gather(*jurisdiction_tasks, return_exceptions=True)
        for result in scanned_rows:
            if isinstance(result, Exception):
                continue
            rows.extend(result)

        if "1.5" in claim_lower and "sbti" not in claim_lower and sbti_status.lower() not in {"validated", "target set"}:
            rows.append({
                "jurisdiction": "UK",
                "framework": "FCA Anti-Greenwashing Rule",
                "status": "gap",
                "specific_violation": "1.5C alignment claim lacks SBTi validation reference",
                "penalty_score": 20,
                "material_misstatement_risk": True,
                "evidence_url": None,
                "remediation_required": "Disclose SBTi validation status and boundary",
            })

        if any(k in claim_lower for k in ["net zero", "net-zero"]) and not any(k in claim_lower for k in ["removal", "capture", "ccs"]):
            rows.append({
                "jurisdiction": "Global",
                "framework": "IPCC Consistency Check",
                "status": "gap",
                "specific_violation": "Net-zero claim omits explicit carbon removal pathway",
                "penalty_score": 15,
                "material_misstatement_risk": True,
                "evidence_url": None,
                "remediation_required": "Publish removals and residual emissions treatment",
            })

        litigation_hits = self._litigation_hits(company, evidence)
        for hit in litigation_hits[:3]:
            rows.append({
                "jurisdiction": hit.get("jurisdiction", "Global"),
                "framework": "Active Enforcement / Litigation",
                "status": "active_enforcement",
                "specific_violation": hit.get("summary", "Active climate-related legal action"),
                "penalty_score": 25,
                "material_misstatement_risk": True,
                "evidence_url": hit.get("url"),
                "remediation_required": "Provide court-compliant remediation and disclosure updates",
            })

        return rows

    async def _scan_jurisdiction(
        self,
        jurisdiction: str,
        company: str,
        claim_text: str,
        evidence: List[Dict[str, Any]],
        sbti_status: str,
    ) -> List[Dict[str, Any]]:
        search_results = await asyncio.to_thread(self._search_official_sources, jurisdiction, company, claim_text)
        combined_text = " ".join([
            claim_text,
            " ".join(str(ev.get("title", "")) + " " + str(ev.get("snippet", "")) for ev in evidence[:10]),
        ]).lower()

        rows: List[Dict[str, Any]] = []
        if not search_results:
            rows.append({
                "jurisdiction": jurisdiction,
                "framework": f"{jurisdiction} Public Evidence Scan",
                "status": "uncertain",
                "specific_violation": "No official source results located in the free scan window",
                "penalty_score": 4,
                "material_misstatement_risk": False,
                "evidence_url": None,
                "remediation_required": "Expand jurisdiction-specific disclosures and public evidence trail",
            })
            return rows

        for item in search_results:
            title = str(item.get("title") or "")
            snippet = str(item.get("snippet") or "")
            url = str(item.get("url") or "")
            text = f"{title} {snippet} {combined_text}".lower()
            status, penalty, violation, remediation = self._score_jurisdiction_result(jurisdiction, text, claim_text, sbti_status)
            rows.append({
                "jurisdiction": jurisdiction,
                "framework": item.get("framework") or f"{jurisdiction} Official Evidence Scan",
                "status": status,
                "specific_violation": violation,
                "penalty_score": penalty,
                "material_misstatement_risk": status in {"gap", "active_enforcement"},
                "evidence_url": url,
                "remediation_required": remediation,
                "source_name": item.get("source_name") or item.get("source") or "Official Search",
            })
        return rows

    def _search_official_sources(self, jurisdiction: str, company: str, claim_text: str) -> List[Dict[str, Any]]:
        domains = self.jurisdiction_domains.get(jurisdiction, self.jurisdiction_domains["Global"])
        claim_terms = " ".join([w for w in re.findall(r"[A-Za-z0-9\-]+", claim_text)[:8] if len(w) > 2])
        query = f'("{company}" {claim_terms}) ' + " OR ".join([f"site:{domain}" for domain in domains])
        results: List[Dict[str, Any]] = []
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=4):
                    url = str(item.get("href") or item.get("url") or "")
                    if not url:
                        continue
                    results.append({
                        "url": url,
                        "title": item.get("title", "Official source"),
                        "snippet": item.get("body", ""),
                        "source_name": self._source_name_for_url(url, jurisdiction),
                        "source": self._source_name_for_url(url, jurisdiction),
                        "framework": self._framework_for_jurisdiction(jurisdiction),
                    })
        except Exception:
            return []
        return results

    def _source_name_for_url(self, url: str, jurisdiction: str) -> str:
        lower = (url or "").lower()
        if "fca" in lower:
            return "FCA"
        if "eur-lex" in lower or "ec.europa" in lower:
            return "EU Official"
        if "rechtspraak" in lower:
            return "Dutch Court"
        if "afm" in lower:
            return "AFM"
        if "sec.gov" in lower:
            return "SEC EDGAR"
        if "ftc.gov" in lower:
            return "FTC"
        if "gov.uk" in lower:
            return "UK Government"
        if jurisdiction == "Global":
            return "Global Framework"
        return f"{jurisdiction} Official"

    def _framework_for_jurisdiction(self, jurisdiction: str) -> str:
        return {
            "UK": "UK Regulatory Evidence Scan",
            "EU": "EU Regulatory Evidence Scan",
            "Netherlands": "Dutch Regulatory Evidence Scan",
            "US": "US Regulatory Evidence Scan",
            "Global": "Global Framework Evidence Scan",
        }.get(jurisdiction, f"{jurisdiction} Evidence Scan")

    def _score_jurisdiction_result(self, jurisdiction: str, text: str, claim_text: str, sbti_status: str) -> tuple[str, int, str, str]:
        if any(k in text for k in ["lawsuit", "ruling", "judgment", "judgement", "court", "enforcement", "fine", "investigation"]):
            return (
                "active_enforcement",
                25,
                f"{jurisdiction} legal or enforcement signal contradicts the public claim",
                "Publish the court/regulator outcome and revise the claim boundary",
            )
        if jurisdiction == "Netherlands" and any(k in text for k in ["afm", "greenwashing", "misleading", "sustainability"]):
            return (
                "gap",
                18,
                "Dutch sustainability oversight flags potential greenwashing risk",
                "Provide Dutch-specific disclosure basis and substantiation trail",
            )
        if jurisdiction == "EU" and any(k in text for k in ["csrd", "taxonomy", "sfdr", "double materiality"]):
            if any(k in claim_text.lower() for k in ["sustainable", "net zero", "1.5"]):
                return (
                    "gap",
                    12,
                    "EU disclosure framework requires explicit substantiation for the sustainability claim",
                    "Add ESRS / taxonomy evidence and boundary definitions",
                )
        if jurisdiction in {"UK", "Global"} and "1.5" in claim_text.lower() and sbti_status.lower() not in {"validated", "target set"}:
            return (
                "gap",
                16,
                "1.5C alignment remains unvalidated against public target evidence",
                "Disclose SBTi validation or clarify aspirational status",
            )
        if any(k in text for k in ["validated", "assured", "verified", "approved"]):
            return (
                "compliant",
                0,
                "Official evidence supports the framework check",
                "Maintain the same disclosure standard in future reporting cycles",
            )
        return (
            "uncertain",
            5,
            "Official source located but no direct substantiation found",
            "Add jurisdiction-specific public evidence or assurance references",
        )

    def _infer_framework_jurisdiction(self, framework: str, jurisdictions: List[str]) -> str:
        low = framework.lower()
        if "eu" in low or "csrd" in low or "sfdr" in low:
            return "EU"
        if "fca" in low or "uk" in low or "tcfd" in low:
            return "UK"
        if "sec" in low or "ftc" in low:
            return "US"
        if "dutch" in low or "afm" in low or "netherlands" in low:
            return "Netherlands"
        return jurisdictions[0] if jurisdictions else "Global"

    def _litigation_hits(self, company: str, evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        hits = []
        token = (company or "").lower().split()[0] if company else ""
        for item in evidence or []:
            if not isinstance(item, dict):
                continue
            text = " ".join([
                str(item.get("title", "")),
                str(item.get("snippet", "")),
                str(item.get("relevant_text", "")),
            ]).lower()
            if token and token not in text:
                continue
            if any(k in text for k in ["lawsuit", "court", "ruling", "enforcement", "greenwashing case"]):
                hits.append({
                    "summary": str(item.get("title") or item.get("snippet") or "Climate litigation signal")[:200],
                    "url": item.get("url"),
                    "jurisdiction": "Netherlands" if "dutch" in text else "Global",
                })
        return hits
