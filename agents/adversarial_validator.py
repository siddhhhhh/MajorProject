from typing import Any, Dict, List


class AdversarialEvidenceValidator:
    def __init__(self) -> None:
        self.name = "Source Adversarial Validator"
        self.credibility_tiers = {
            "government_regulatory": 0.95,
            "peer_reviewed_academic": 0.90,
            "cdp_verified": 0.88,
            "major_news_outlet": 0.75,
            "ngo_established": 0.70,
            "investigative_journalism": 0.68,
            "general_web": 0.45,
            "company_self_report": 0.30,
        }

    def triangulate(self, company: str, claim_text: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        classified: List[Dict[str, Any]] = []
        support_weight = 0.0
        contradict_weight = 0.0
        neutral_count = 0
        first_party_count = 0

        for idx, item in enumerate(evidence or [], start=1):
            if not isinstance(item, dict):
                continue
            src_name = str(item.get("source_name") or item.get("source") or f"source_{idx}")
            src_type = str(item.get("source_type") or "general_web").lower()
            text_blob = " ".join([
                str(item.get("title", "")),
                str(item.get("snippet", "")),
                str(item.get("relevant_text", "")),
            ]).lower()

            stance = self._stance_for_text(claim_text, text_blob)
            tier = self._tier_for_source(src_name, src_type)
            credibility = self.credibility_tiers[tier]
            is_first_party = self._is_first_party(company, src_name, item)
            if is_first_party:
                first_party_count += 1
                credibility = min(credibility, 0.30)
                # First-party disclosures support the issuer's own claim by default.
                stance = "SUPPORTS"

            row = {
                "source_id": item.get("source_id") or f"ev_{idx:03d}",
                "source_name": src_name,
                "stance": stance,
                "credibility": round(credibility, 2),
                "source_type": tier,
                "is_first_party": is_first_party,
                "key_evidence": str(item.get("snippet") or item.get("title") or "")[:240],
            }
            classified.append(row)

            if stance == "SUPPORTS":
                support_weight += credibility
            elif stance == "CONTRADICTS":
                contradict_weight += credibility
            else:
                neutral_count += 1

        total_weight = support_weight + contradict_weight
        adversarial_ratio = (contradict_weight / total_weight) if total_weight > 0 else 0.0

        triangulation_score = 50.0
        if total_weight > 0:
            triangulation_score = (support_weight / total_weight) * 100
        if contradict_weight > support_weight and contradict_weight > 0:
            triangulation_score = max(0.0, triangulation_score - 10.0)
        triangulation_score = max(0.0, min(100.0, triangulation_score))

        supporting_count = len([c for c in classified if c.get("stance") == "SUPPORTS"])
        contradicting_count = len([c for c in classified if c.get("stance") == "CONTRADICTS"])

        if supporting_count == 0 and contradicting_count == 0:
            triangulation_score = None
            evidence_balance = "UNCLASSIFIED — Stance classification failed"
        elif adversarial_ratio > 0.6:
            evidence_balance = "PREDOMINANTLY_CONTRADICTED"
        elif adversarial_ratio < 0.3:
            evidence_balance = "PREDOMINANTLY_SUPPORTED"
        else:
            evidence_balance = "MIXED"

        most_damaging = ""
        contradicting = [c for c in classified if c.get("stance") == "CONTRADICTS"]
        if contradicting:
            contradicting.sort(key=lambda c: float(c.get("credibility", 0.0)), reverse=True)
            top = contradicting[0]
            most_damaging = f"{top.get('source_name')}: {top.get('key_evidence')}"

        return {
            "source_stances": classified,
            "triangulation_score": round(triangulation_score, 1) if isinstance(triangulation_score, (int, float)) else None,
            "adversarial_ratio": round(adversarial_ratio, 2),
            "most_damaging_evidence": most_damaging,
            "evidence_balance": evidence_balance,
            "first_party_bias_warning": bool(first_party_count > 0),
            "first_party_source_count": first_party_count,
            "corroborating_sources": supporting_count,
            "contradicting_sources": contradicting_count,
            "neutral_sources": neutral_count,
            "recommendation": self._recommendation_for_score(triangulation_score if isinstance(triangulation_score, (int, float)) else 50.0),
        }

    def _tier_for_source(self, source_name: str, source_type: str) -> str:
        s = source_name.lower()
        t = source_type.lower()
        if any(k in s or k in t for k in ["sec", "europa", "gov", "fca", "afm", "court", "regulatory"]):
            return "government_regulatory"
        if any(k in s or k in t for k in ["journal", "academic", "university", "peer-reviewed"]):
            return "peer_reviewed_academic"
        if any(k in s or k in t for k in ["cdp", "sbti"]):
            return "cdp_verified"
        if any(k in s for k in ["reuters", "bloomberg", "ft", "bbc", "ap"]):
            return "major_news_outlet"
        if any(k in s for k in ["clientearth", "influencemap", "reclaim", "greenpeace", "amnesty"]):
            return "ngo_established"
        if any(k in t for k in ["investigative", "investigation"]):
            return "investigative_journalism"
        if any(k in t for k in ["company", "company-controlled", "investor relations"]):
            return "company_self_report"
        return "general_web"

    def _stance_for_text(self, claim: str, evidence_text: str) -> str:
        c = claim.lower()
        e = evidence_text.lower()
        contradict_terms = ["lawsuit", "greenwashing", "misleading", "failed", "gap", "overstated", "not aligned", "critic"]
        support_terms = ["achieved", "validated", "assured", "verified", "on track", "met target"]

        contrad = sum(1 for k in contradict_terms if k in e)
        support = sum(1 for k in support_terms if k in e)

        if contrad > support and contrad > 0:
            return "CONTRADICTS"
        if support > contrad and support > 0:
            return "SUPPORTS"

        # If claim says alignment but evidence lacks verification language, treat as mixed.
        if ("1.5" in c or "net zero" in c) and not any(k in e for k in ["sbti", "validated", "assurance"]):
            return "MIXED"
        return "NEUTRAL"

    def _is_first_party(self, company: str, source_name: str, item: Dict[str, Any]) -> bool:
        domain = str(item.get("url") or "").lower()
        src = source_name.lower()
        token = company.lower().split()[0] if company else ""
        return bool(token and (token in src or token in domain))

    def _recommendation_for_score(self, score: float) -> str:
        if score < 40:
            return "Claim should be treated as high-risk until independent verification offsets contradicting evidence."
        if score < 60:
            return "Claim is mixed; require additional third-party evidence before relying on company statements."
        return "Claim has moderate-to-strong triangulated support, continue monitoring for new contradictions."
