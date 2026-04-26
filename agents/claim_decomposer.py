import json
import re
from typing import Any, Dict, List

from core.llm_call import call_llm
import asyncio


CLAIM_DECOMPOSITION_PROMPT = """
You are an expert ESG analyst specialising in corporate climate claim verification.

TASK: Decompose the following compound ESG claim into atomic, independently verifiable sub-claims.

COMPANY: {company}
INDUSTRY: {industry}
ORIGINAL CLAIM: {claim_text}

INSTRUCTIONS:
1. Split the claim at logical conjunctions: and, while, as well as, in addition to, alongside
1b. Also split implicit assertions even without conjunctions, including:
   - Comparative claims (e.g., "reduces emissions") that require a baseline comparison
   - Vague quantifiers (e.g., "significantly", "substantially", "meaningfully") that require numeric thresholds
   - Geographic scope claims (e.g., "global", "across all markets") that require coverage evidence
   - Causal mechanism claims (e.g., "through X") that require mechanism validation
2. Identify each distinct commitment, target, or assertion
3. Flag logical tensions between sub-claims (e.g., growing fossil fuel production cannot coexist with Scope 3 reduction)
4. For each sub-claim, state what evidence WOULD be needed to verify it
5. Assign a greenwashing_signal from [red_flag, amber_flag, green_flag, unverifiable] based on internal logic alone
6. If a claim is longer than 10 words and you return only 1 sub-claim, re-check for implicit assertions and decompose further.

Return ONLY valid JSON.
"""


class ClaimDecomposer:
    def __init__(self) -> None:
        self.name = "Claim Decomposition Agent"

    def decompose_claim(self, company: str, industry: str, claim_text: str) -> Dict[str, Any]:
        if not claim_text:
            return {
                "original_claim": "",
                "sub_claims": [],
                "logical_tension_pairs": [],
                "overall_internal_consistency": "consistent",
                "decomposition_confidence": 0.0,
            }

        llm_result = self._try_llm(company, industry, claim_text)
        if llm_result:
            processed = self._post_process(llm_result, claim_text)
            words = len(re.findall(r"\w+", claim_text or ""))
            if words > 10 and len(processed.get("sub_claims", [])) < 2:
                # Retry once with stronger decomposition constraints for implicit assertions.
                retry_result = self._try_llm(company, industry, claim_text, force_retry=True)
                if retry_result:
                    processed_retry = self._post_process(retry_result, claim_text)
                    if len(processed_retry.get("sub_claims", [])) >= 2:
                        return processed_retry
            return processed

        return self._heuristic_decomposition(claim_text)

    def compute_internal_contradiction_score(self, tension_pairs: List[Dict[str, Any]]) -> float:
        severity_weights = {"high": 1.0, "medium": 0.6, "low": 0.2}
        type_multipliers = {
            "physical_impossibility": 1.5,
            "goal_conflict": 1.2,
            "timeline_clash": 0.9,
            "scope_boundary_issue": 0.8,
        }
        score = 0.0
        for pair in tension_pairs or []:
            sev = str(pair.get("severity", "low")).lower()
            ttype = str(pair.get("tension_type", "scope_boundary_issue")).lower()
            w = severity_weights.get(sev, 0.2)
            m = type_multipliers.get(ttype, 0.8)
            score += w * m * 25
        return float(min(score, 100.0))

    def _try_llm(self, company: str, industry: str, claim_text: str, force_retry: bool = False) -> Dict[str, Any]:
        prompt = CLAIM_DECOMPOSITION_PROMPT.format(
            company=company,
            industry=industry,
            claim_text=claim_text,
        )
        if force_retry:
            prompt += (
                "\n\nRETRY INSTRUCTION: You returned only 1 sub-claim earlier. "
                "Re-examine implicit assertions, vague qualifiers, and scope language "
                "and return at least 2 atomic sub-claims where applicable."
            )
        try:
            response = asyncio.run(call_llm("claim_decomposition", prompt))
            if not response:
                return {}
            cleaned = self._clean_json_response(response)
            payload = json.loads(cleaned)
            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}
        return {}

    def _heuristic_decomposition(self, claim_text: str) -> Dict[str, Any]:
        split_pattern = r"\b(?:and|while|as well as|in addition to|alongside)\b"
        parts = [p.strip(" ,.;") for p in re.split(split_pattern, claim_text, flags=re.IGNORECASE) if p.strip()]
        if len(parts) == 1:
            parts = [claim_text.strip()]

        lower_claim = claim_text.lower()
        implicit_parts: List[str] = []
        if any(tok in lower_claim for tok in ["reduces", "reduction", "lower than", "decrease"]):
            implicit_parts.append("Claim implies comparative baseline against counterfactual emissions scenario.")
        if any(tok in lower_claim for tok in ["significantly", "substantially", "meaningfully"]):
            implicit_parts.append("Claim uses vague quantifier requiring explicit numeric threshold for verification.")
        if any(tok in lower_claim for tok in ["global", "globally", "across all"]):
            implicit_parts.append("Claim asserts geographic scope requiring multi-region evidence coverage.")
        if "through " in lower_claim:
            implicit_parts.append("Claim asserts causal mechanism requiring mechanism-specific evidence.")

        if len(parts) == 1 and len(re.findall(r"\w+", claim_text)) > 10 and implicit_parts:
            parts.extend(implicit_parts[:3])

        sub_claims: List[Dict[str, Any]] = []
        for idx, part in enumerate(parts, start=1):
            lowered = part.lower()
            claim_type = "policy_claim"
            if "scope" in lowered or "%" in lowered or re.search(r"\b\d{4}\b", lowered):
                claim_type = "quantitative_target"
            if "net zero" in lowered or "1.5" in lowered or "aligned" in lowered:
                claim_type = "alignment_claim"
            if "production" in lowered or "oil" in lowered or "gas" in lowered:
                claim_type = "production_claim"

            sub_claims.append({
                "id": f"SC{idx}",
                "text": part,
                "type": claim_type,
                "pillar": "E",
                "measurable": bool(re.search(r"\b\d+(?:\.\d+)?\b|scope\s*[123]", lowered)),
                "verification_requirements": self._verification_requirements(part),
                "greenwashing_signal": self._signal_for_subclaim(part),
            })

        tensions = self._detect_tensions(sub_claims)
        score = self.compute_internal_contradiction_score(tensions)

        consistency = "consistent"
        if score > 60:
            consistency = "severely_inconsistent"
        elif score > 20:
            consistency = "mildly_inconsistent"

        return {
            "original_claim": claim_text,
            "sub_claims": sub_claims,
            "logical_tension_pairs": tensions,
            "overall_internal_consistency": consistency,
            "decomposition_confidence": 0.68,
        }

    def _post_process(self, payload: Dict[str, Any], claim_text: str) -> Dict[str, Any]:
        sub_claims = payload.get("sub_claims") if isinstance(payload.get("sub_claims"), list) else []
        normalized: List[Dict[str, Any]] = []
        for idx, sc in enumerate(sub_claims, start=1):
            if not isinstance(sc, dict):
                continue
            normalized.append({
                "id": str(sc.get("id") or f"SC{idx}"),
                "text": str(sc.get("text") or "").strip(),
                "type": str(sc.get("type") or "policy_claim"),
                "pillar": str(sc.get("pillar") or "cross-pillar"),
                "measurable": bool(sc.get("measurable", False)),
                "verification_requirements": sc.get("verification_requirements") if isinstance(sc.get("verification_requirements"), list) else self._verification_requirements(str(sc.get("text") or "")),
                "greenwashing_signal": str(sc.get("greenwashing_signal") or "unverifiable"),
            })

        tensions = payload.get("logical_tension_pairs") if isinstance(payload.get("logical_tension_pairs"), list) else []
        normalized_tensions = [t for t in tensions if isinstance(t, dict)]
        if not normalized_tensions:
            normalized_tensions = self._detect_tensions(normalized)

        score = self.compute_internal_contradiction_score(normalized_tensions)
        consistency = payload.get("overall_internal_consistency")
        if not consistency:
            consistency = "consistent" if score <= 20 else "mildly_inconsistent" if score <= 60 else "severely_inconsistent"

        return {
            "original_claim": payload.get("original_claim") or claim_text,
            "sub_claims": normalized or self._heuristic_decomposition(claim_text).get("sub_claims", []),
            "logical_tension_pairs": normalized_tensions,
            "overall_internal_consistency": consistency,
            "decomposition_confidence": float(payload.get("decomposition_confidence", 0.72)),
        }

    def _detect_tensions(self, sub_claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tensions: List[Dict[str, Any]] = []
        for i in range(len(sub_claims)):
            for j in range(i + 1, len(sub_claims)):
                a = sub_claims[i]
                b = sub_claims[j]
                a_text = str(a.get("text", "")).lower()
                b_text = str(b.get("text", "")).lower()
                pair_text = f"{a_text} {b_text}"

                production_growth = any(k in pair_text for k in ["production growth", "maintain production", "increase production", "grow oil", "grow gas"])
                scope3_reduction = ("scope 3" in pair_text) and any(k in pair_text for k in ["reduce", "reduction", "cut", "decrease"])

                if production_growth and scope3_reduction:
                    tensions.append({
                        "claim_a": a.get("id"),
                        "claim_b": b.get("id"),
                        "tension_type": "physical_impossibility",
                        "tension_description": "Production growth conflicts with absolute Scope 3 reduction in fossil value chains.",
                        "severity": "high",
                    })
                    continue

                if ("1.5" in pair_text or "1.5c" in pair_text) and ("aligned" in pair_text) and ("sbti" not in pair_text):
                    tensions.append({
                        "claim_a": a.get("id"),
                        "claim_b": b.get("id"),
                        "tension_type": "scope_boundary_issue",
                        "tension_description": "1.5C alignment claim lacks validation boundary detail (e.g., SBTi).",
                        "severity": "medium",
                    })

                if ("2030" in pair_text) and not any(k in pair_text for k in ["interim", "milestone", "annual"]):
                    tensions.append({
                        "claim_a": a.get("id"),
                        "claim_b": b.get("id"),
                        "tension_type": "timeline_clash",
                        "tension_description": "Timeline commitments are present without interim milestones.",
                        "severity": "low",
                    })

        dedup: List[Dict[str, Any]] = []
        seen = set()
        for t in tensions:
            key = (t.get("claim_a"), t.get("claim_b"), t.get("tension_type"))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(t)
        return dedup

    def _verification_requirements(self, text: str) -> List[str]:
        lower = text.lower()
        reqs = []
        if "scope" in lower:
            reqs.append("Scope-wise baseline and current emissions data")
            reqs.append("Third-party assurance statement")
        if "net zero" in lower:
            reqs.append("Decarbonization pathway and removals assumptions")
        if "1.5" in lower:
            reqs.append("SBTi or equivalent pathway validation")
        if "production" in lower:
            reqs.append("Production volume forecast and absolute emissions linkage")
        if not reqs:
            reqs.append("Public target disclosure with measurable KPI and year")
        return reqs

    def _signal_for_subclaim(self, text: str) -> str:
        lower = text.lower()
        if any(k in lower for k in ["fully aligned", "world leading", "best in class"]) and not re.search(r"\b\d", lower):
            return "amber_flag"
        if "scope 3" in lower and "production" in lower:
            return "red_flag"
        if any(k in lower for k in ["target", "by 20", "scope", "%"]):
            return "green_flag"
        return "unverifiable"

    @staticmethod
    def _clean_json_response(response: str) -> str:
        cleaned = re.sub(r"```\s*json\s*", "", str(response), flags=re.IGNORECASE)
        cleaned = re.sub(r"```", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start:end + 1]
        return cleaned
