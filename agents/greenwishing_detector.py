"""
Greenwishing/Greenhushing Detector Agent
Detects advanced ESG deception tactics beyond traditional greenwashing

Based on 2025-2026 academic research:
- Greenwishing: Setting unfunded, aspirational goals without credible pathways
- Greenhushing: Deliberately hiding sustainability data to avoid scrutiny
- Selective Disclosure: Cherry-picking favorable ESG data while omitting negative
- Carbon Tunnel Vision: Focusing only on carbon while ignoring other ESG factors

Supports: SEBI BRSR, CSRD, SEC Climate Rules, UK FCA anti-greenwashing
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.llm_client import llm_client
from config.agent_prompts import GREENWISHING_DETECTION_PROMPT


class GreenwishingDetector:
    """
    Advanced ESG Deception Detection Agent
    Beyond greenwashing: Detects greenwishing, greenhushing, and selective disclosure
    """
    
    def __init__(self):
        self.name = "Greenwishing & Greenhushing Detection Specialist"
        self.llm = llm_client
        
        # Greenwishing indicators
        self.greenwishing_indicators = {
            "unfunded_targets": [
                "aim to", "aspire to", "hope to", "intend to", "plan to",
                "looking to", "working towards", "committed to exploring"
            ],
            "vague_timelines": [
                "in the future", "eventually", "sometime", "as soon as possible",
                "when feasible", "when technology allows", "in due course"
            ],
            "no_pathway": [
                "subject to", "depending on", "conditional upon", "if conditions permit",
                "technology-dependent", "market-dependent", "policy-dependent"
            ],
            "aspirational_language": [
                "vision", "dream", "ambition", "aspiration", "long-term goal",
                "ultimate aim", "transformational journey"
            ]
        }
        
        # Greenhushing indicators (required climate disclosure fields)
        self.required_disclosures = {
            "scope1": ["scope 1", "scope i"],
            "scope2": ["scope 2", "scope ii"],
            "scope3": ["scope 3", "scope iii"],
            "renewable_energy_percent": ["renewable", "% renewable", "renewable energy"],
            "net_zero_target_year": ["net zero", "carbon neutral by", "target year"],
            "science_based_targets": ["science based target", "sbti", "science-based"],
            "climate_capex": ["climate capex", "decarbonization capex", "climate investment", "capital expenditure"]
        }
        
        # Indian BRSR mandatory disclosures (for greenhushing detection)
        self.brsr_mandatory_fields = [
            "greenhouse_gas_emissions",
            "energy_consumption",
            "water_withdrawal",
            "water_recycled",
            "waste_by_type",
            "employee_wellbeing",
            "community_engagement",
            "governance_structure"
        ]
        
        # Selective disclosure patterns
        self.selective_disclosure_patterns = {
            "cherry_picking": [
                "best performing", "leading in", "top", "ahead of peers",
                "exceeds industry average", "best-in-class performance"
            ],
            "boundary_manipulation": [
                "operational control", "financial control", "equity share",
                "joint ventures excluded", "subsidiaries not included"
            ],
            "baseline_gaming": [
                "new baseline", "adjusted baseline", "restated figures",
                "methodology change", "boundary change"
            ]
        }
    
    def detect_deception_tactics(self, company: str, claim: Dict[str, Any],
                                 evidence: List[Dict[str, Any]],
                                 historical_data: Dict[str, Any] = None,
                                 structured_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Detect greenwishing, greenhushing, and selective disclosure
        
        Args:
            company: Company name
            claim: ESG claim being analyzed
            evidence: Retrieved evidence documents
            historical_data: Optional historical ESG data for trend analysis
        
        Returns:
            Comprehensive deception analysis
        """
        
        print(f"\n{'='*60}")
        print(f"🔍 AGENT: {self.name}")
        print(f"{'='*60}")
        print(f"Company: {company}")
        print(f"Claim: {claim.get('claim_text', '')[:80]}...")
        
        claim_text = claim.get("claim_text", "")
        evidence_text = self._combine_evidence(evidence)
        context_text = self._combine_structured_context(structured_context or {})
        full_text = f"{evidence_text}\n\n{context_text}".strip()
        
        # 1. Detect Greenwishing
        print("🎯 Detecting greenwishing patterns...")
        greenwishing_analysis = self._detect_greenwishing(claim_text, full_text, company)
        
        # 2. Detect Greenhushing
        print("🔇 Detecting greenhushing patterns...")
        greenhushing_analysis = self._detect_greenhushing(full_text, company, structured_context or {})
        
        # 3. Detect Selective Disclosure
        print("📊 Detecting selective disclosure...")
        selective_disclosure = self._detect_selective_disclosure(claim_text, full_text)
        
        # 4. Carbon Tunnel Vision Check
        print("🔭 Checking for carbon tunnel vision...")
        tunnel_vision = self._detect_carbon_tunnel_vision(full_text)
        
        # 5. LLM Deep Analysis
        print("🤖 Running AI deep analysis...")
        llm_analysis = self._llm_deep_analysis(company, claim_text, full_text)
        
        # 6. Calculate overall deception risk
        deception_risk = self._calculate_deception_risk(
            greenwishing_analysis,
            greenhushing_analysis, 
            selective_disclosure,
            tunnel_vision
        )
        
        result = {
            "company": company,
            "claim_id": claim.get("claim_id"),
            "analysis_timestamp": datetime.now().isoformat(),
            "greenwishing": greenwishing_analysis,
            "greenhushing": greenhushing_analysis,
            "selective_disclosure": selective_disclosure,
            "carbon_tunnel_vision": tunnel_vision,
            "llm_analysis": llm_analysis,
            "overall_deception_risk": deception_risk,
            "recommendations": self._generate_recommendations(deception_risk)
        }
        
        print(f"\n✅ Deception detection complete:")
        print(f"   Greenwishing score: {greenwishing_analysis['score']}/100")
        print(f"   Greenhushing score: {greenhushing_analysis['score']}/100")
        print(f"   Selective disclosure: {selective_disclosure['score']}/100")
        print(f"   Overall deception risk: {deception_risk['level']}")
        
        return result
    
    def _combine_evidence(self, evidence: List[Dict[str, Any]]) -> str:
        """Combine evidence into searchable text"""
        texts = []
        for ev in evidence[:15]:
            title = ev.get("title", "")
            snippet = ev.get("snippet", ev.get("relevant_text", ""))
            texts.append(f"{title}: {snippet}")
        return "\n\n".join(texts)[:10000]

    def _combine_structured_context(self, structured_context: Dict[str, Any]) -> str:
        """Merge report chunks, report claims, and carbon extraction into searchable text."""
        texts = []

        report_chunks = structured_context.get("report_chunks", [])
        for chunk in report_chunks[:20]:
            if isinstance(chunk, dict):
                txt = str(chunk.get("text", "")).strip()
                if txt:
                    texts.append(txt[:600])

        report_claims_by_year = structured_context.get("report_claims_by_year", {})
        if isinstance(report_claims_by_year, dict):
            for year, claims in report_claims_by_year.items():
                if isinstance(claims, list):
                    for c in claims[:15]:
                        texts.append(f"{year}: {str(c)}")

        carbon = structured_context.get("carbon_extraction", {})
        if isinstance(carbon, dict):
            emissions = carbon.get("emissions", {})
            if isinstance(emissions, dict):
                for scope_key in ["scope1", "scope2", "scope3"]:
                    scope = emissions.get(scope_key, {})
                    if isinstance(scope, dict):
                        val = scope.get("value") or scope.get("total")
                        if val not in [None, "N/A"]:
                            texts.append(f"{scope_key} emissions {val}")

            if carbon.get("net_zero_target"):
                texts.append(f"net zero target {carbon.get('net_zero_target')}")
            if carbon.get("renewable_energy_percentage"):
                texts.append(f"renewable energy {carbon.get('renewable_energy_percentage')}")
            if carbon.get("science_based_target"):
                texts.append("science based targets sbti")

        return "\n".join(texts)[:12000]

    def _has_structured_disclosure(self, category: str, structured_context: Dict[str, Any]) -> bool:
        """Check if a required disclosure category is present in structured outputs."""
        carbon = structured_context.get("carbon_extraction", {})
        if not isinstance(carbon, dict):
            carbon = {}

        emissions = carbon.get("emissions", {})
        if not isinstance(emissions, dict):
            emissions = {}

        if category == "scope1":
            s1 = emissions.get("scope1", {})
            return isinstance(s1, dict) and (s1.get("value") not in [None, "N/A"])
        if category == "scope2":
            s2 = emissions.get("scope2", {})
            return isinstance(s2, dict) and (s2.get("value") not in [None, "N/A"])
        if category == "scope3":
            s3 = emissions.get("scope3", {})
            if isinstance(s3, dict):
                return (s3.get("value") not in [None, "N/A"]) or (s3.get("total") not in [None, "N/A"])
            return False
        if category == "renewable_energy_percent":
            return bool(carbon.get("renewable_energy_percentage"))
        if category == "net_zero_target_year":
            return bool(carbon.get("net_zero_target"))
        if category == "science_based_targets":
            return bool(carbon.get("science_based_target"))
        if category == "climate_capex":
            return bool(carbon.get("climate_capex"))

        return False
    
    def _detect_greenwishing(self, claim_text: str, evidence_text: str, 
                            company: str) -> Dict[str, Any]:
        """
        Detect greenwishing: Unfunded, aspirational goals without credible pathways
        """
        
        findings = []
        claim_lower = claim_text.lower()
        evidence_lower = evidence_text.lower()
        combined_text = claim_lower + " " + evidence_lower
        
        # Check unfunded targets
        unfunded_matches = []
        for phrase in self.greenwishing_indicators["unfunded_targets"]:
            if phrase in claim_lower:
                unfunded_matches.append(phrase)
        
        if unfunded_matches:
            findings.append({
                "type": "unfunded_target_language",
                "matches": unfunded_matches,
                "severity": "High" if len(unfunded_matches) >= 2 else "Medium"
            })
        
        # Check vague timelines
        vague_timeline_matches = []
        for phrase in self.greenwishing_indicators["vague_timelines"]:
            if phrase in combined_text:
                vague_timeline_matches.append(phrase)
        
        if vague_timeline_matches:
            findings.append({
                "type": "vague_timeline",
                "matches": vague_timeline_matches,
                "severity": "Medium"
            })
        
        # Check for missing pathway/funding
        pathway_issues = []
        for phrase in self.greenwishing_indicators["no_pathway"]:
            if phrase in combined_text:
                pathway_issues.append(phrase)
        
        if pathway_issues:
            findings.append({
                "type": "no_clear_pathway",
                "matches": pathway_issues,
                "severity": "High"
            })
        
        # Check aspirational vs concrete language ratio
        aspirational_count = sum(
            1 for phrase in self.greenwishing_indicators["aspirational_language"]
            if phrase in combined_text
        )
        
        concrete_indicators = ["investment of", "allocated", "budget of", "funding", 
                              "capex", "spent", "deployed capital"]
        concrete_count = sum(1 for phrase in concrete_indicators if phrase in combined_text)
        
        if aspirational_count > concrete_count * 2:
            findings.append({
                "type": "aspirational_imbalance",
                "detail": f"Aspirational language ({aspirational_count}) >> Concrete language ({concrete_count})",
                "severity": "Medium"
            })
        
        # Check for commitment without CAPEX
        if any(word in combined_text for word in ["net zero", "carbon neutral", "100% renewable"]):
            if not any(word in combined_text for word in ["invest", "capex", "capital expenditure", 
                                                          "budget", "funding", "crore", "million"]):
                findings.append({
                    "type": "commitment_without_capex",
                    "detail": "Major commitment without disclosed capital expenditure",
                    "severity": "High"
                })
        
        # Calculate score
        severity_weights = {"High": 30, "Medium": 20, "Low": 10}
        score = min(100, sum(severity_weights.get(f["severity"], 10) for f in findings))
        
        return {
            "detected": len(findings) > 0,
            "findings": findings,
            "score": score,
            "risk_level": "High" if score >= 60 else "Medium" if score >= 30 else "Low",
            "definition": "Greenwishing: Setting unfunded, aspirational sustainability goals without credible implementation pathways"
        }
    
    def _detect_greenhushing(self, evidence_text: str, company: str, structured_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Detect greenhushing: Deliberately hiding sustainability data
        """
        
        findings = []
        structured_context = structured_context or {}
        evidence_lower = evidence_text.lower()
        
        # Check required disclosure completeness
        missing_disclosure_count = 0
        disclosed_count = 0
        total_fields = len(self.required_disclosures)

        for category, keywords in self.required_disclosures.items():
            category_found = any(kw in evidence_lower for kw in keywords) or self._has_structured_disclosure(category, structured_context)

            if not category_found:
                missing_disclosure_count += 1
                findings.append({
                    "type": "missing_mandatory_disclosure",
                    "category": category,
                    "expected_keywords": keywords[:3],
                    "severity": "High" if category in ["scope1", "scope2", "scope3"] else "Medium"
                })
            else:
                disclosed_count += 1
        
        # Check BRSR compliance (for Indian companies or listed entities)
        brsr_missing = []
        for field in self.brsr_mandatory_fields:
            field_readable = field.replace("_", " ")
            if field_readable not in evidence_lower and field not in evidence_lower:
                brsr_missing.append(field)
        
        if len(brsr_missing) > len(self.brsr_mandatory_fields) * 0.5:
            findings.append({
                "type": "brsr_disclosure_gap",
                "missing_fields": brsr_missing[:5],
                "compliance_rate": f"{(len(self.brsr_mandatory_fields) - len(brsr_missing)) / len(self.brsr_mandatory_fields) * 100:.0f}%",
                "severity": "High"
            })
        
        # Check for deliberate suppression indicators
        suppression_indicators = [
            "confidential commercial reasons",
            "proprietary information",
            "competitive sensitivity",
            "data not collected",
            "not applicable",
            "not material"
        ]
        
        suppression_matches = [ind for ind in suppression_indicators if ind in evidence_lower]
        if suppression_matches:
            findings.append({
                "type": "suppression_language",
                "matches": suppression_matches,
                "severity": "Medium"
            })
        
        # Check for partial year reporting
        if "q1" in evidence_lower or "q2" in evidence_lower or "q3" in evidence_lower:
            if "full year" not in evidence_lower and "annual" not in evidence_lower:
                findings.append({
                    "type": "partial_period_reporting",
                    "detail": "Partial year data without full annual disclosure",
                    "severity": "Low"
                })
        
        # Greenhushing score based on missing_fields / total_fields
        if missing_disclosure_count == 0:
            score = 0
            print(f"[Fix] Greenhushing score corrected: All disclosures present, score = 0")
        else:
            completeness_ratio = disclosed_count / max(total_fields, 1)
            score = int(round((missing_disclosure_count / max(total_fields, 1)) * 100))

            # If company discloses >70%, keep greenhushing low
            if completeness_ratio > 0.70:
                score = min(score, 30)

            print(
                f"[Fix] Greenhushing completeness={completeness_ratio:.2f}, "
                f"missing={missing_disclosure_count}/{total_fields}, score={score}"
            )
        
        return {
            "detected": len(findings) > 0,
            "findings": findings,
            "score": score,
            "disclosure_completeness": round(disclosed_count / max(total_fields, 1), 2),
            "missing_fields": missing_disclosure_count,
            "total_fields": total_fields,
            "risk_level": "High" if score >= 50 else "Medium" if score >= 25 else "Low",
            "definition": "Greenhushing: Deliberately underreporting or hiding sustainability data to avoid scrutiny"
        }
    
    def _detect_selective_disclosure(self, claim_text: str, 
                                     evidence_text: str) -> Dict[str, Any]:
        """
        Detect selective disclosure: Cherry-picking favorable data
        """
        
        findings = []
        combined_lower = (claim_text + " " + evidence_text).lower()
        
        # Check cherry-picking language
        for phrase in self.selective_disclosure_patterns["cherry_picking"]:
            if phrase in combined_lower:
                findings.append({
                    "type": "cherry_picking_language",
                    "phrase": phrase,
                    "severity": "Medium"
                })
        
        # Check boundary manipulation
        for phrase in self.selective_disclosure_patterns["boundary_manipulation"]:
            if phrase in combined_lower:
                findings.append({
                    "type": "boundary_manipulation",
                    "phrase": phrase,
                    "detail": "Organizational boundary language that may exclude material emissions",
                    "severity": "High"
                })
        
        # Check baseline gaming
        for phrase in self.selective_disclosure_patterns["baseline_gaming"]:
            if phrase in combined_lower:
                findings.append({
                    "type": "baseline_manipulation",
                    "phrase": phrase,
                    "severity": "High"
                })
        
        # Check for positive-only reporting
        positive_words = ["improved", "increased", "exceeded", "outperformed", "achieved", "success"]
        negative_words = ["declined", "increased emissions", "missed target", "challenge", "setback"]
        
        positive_count = sum(1 for w in positive_words if w in combined_lower)
        negative_count = sum(1 for w in negative_words if w in combined_lower)
        
        if positive_count > 3 and negative_count == 0:
            findings.append({
                "type": "positive_only_reporting",
                "detail": f"Only positive outcomes reported ({positive_count} positive, {negative_count} negative)",
                "severity": "Medium"
            })
        
        # Check for omitted peer comparison
        if "industry average" in combined_lower or "peers" in combined_lower:
            if "below average" not in combined_lower and "underperform" not in combined_lower:
                if "above average" in combined_lower or "outperform" in combined_lower:
                    findings.append({
                        "type": "selective_peer_comparison",
                        "detail": "Only favorable peer comparisons shown",
                        "severity": "Low"
                    })
        
        # Calculate score
        severity_weights = {"High": 30, "Medium": 20, "Low": 10}
        score = min(100, sum(severity_weights.get(f.get("severity"), 10) for f in findings))
        
        return {
            "detected": len(findings) > 0,
            "findings": findings,
            "score": score,
            "risk_level": "High" if score >= 50 else "Medium" if score >= 25 else "Low"
        }
    
    def _detect_carbon_tunnel_vision(self, evidence_text: str) -> Dict[str, Any]:
        """
        Detect carbon tunnel vision: Focus only on carbon while ignoring other ESG
        """
        
        evidence_lower = evidence_text.lower()
        
        # Count mentions of different ESG categories
        carbon_terms = ["carbon", "co2", "emissions", "ghg", "greenhouse", "scope 1", 
                       "scope 2", "scope 3", "net zero", "decarbonization"]
        
        other_e_terms = ["water", "waste", "biodiversity", "pollution", "deforestation",
                        "plastic", "recycling", "circular economy"]
        
        social_terms = ["employee", "worker", "safety", "diversity", "human rights",
                       "community", "labor", "supply chain workers"]
        
        governance_terms = ["board", "governance", "ethics", "corruption", "transparency",
                          "executive pay", "audit", "compliance"]
        
        carbon_count = sum(1 for term in carbon_terms if term in evidence_lower)
        other_e_count = sum(1 for term in other_e_terms if term in evidence_lower)
        social_count = sum(1 for term in social_terms if term in evidence_lower)
        governance_count = sum(1 for term in governance_terms if term in evidence_lower)
        
        total_esg = carbon_count + other_e_count + social_count + governance_count
        
        tunnel_vision_detected = False
        imbalance_detail = ""
        
        if total_esg > 0:
            carbon_percentage = (carbon_count / total_esg) * 100
            
            if carbon_percentage > 70:
                tunnel_vision_detected = True
                imbalance_detail = f"Carbon topics: {carbon_percentage:.0f}% of ESG mentions"
        
        return {
            "detected": tunnel_vision_detected,
            "carbon_focus_percentage": (carbon_count / max(total_esg, 1)) * 100,
            "topic_breakdown": {
                "carbon_climate": carbon_count,
                "other_environmental": other_e_count,
                "social": social_count,
                "governance": governance_count
            },
            "imbalance_detail": imbalance_detail,
            "risk_level": "High" if tunnel_vision_detected else "Low",
            "definition": "Carbon Tunnel Vision: Disproportionate focus on carbon while neglecting other material ESG factors"
        }
    
    def _llm_deep_analysis(self, company: str, claim_text: str, 
                          evidence_text: str) -> Dict[str, Any]:
        """Use LLM for nuanced deception pattern detection"""
        
        prompt = f"""{GREENWISHING_DETECTION_PROMPT}

COMPANY: {company}
CLAIM: {claim_text}

EVIDENCE:
{evidence_text[:5000]}

Analyze for greenwishing, greenhushing, and selective disclosure. Return JSON."""
        
        response = self.llm.call_with_fallback(prompt, use_gemini_first=True)
        
        if not response:
            return {"analysis_performed": False, "error": "LLM call failed"}
        
        try:
            cleaned = re.sub(r'```\s*json?\s*', '', response)
            cleaned = re.sub(r'```\s*', '', cleaned)
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
        except:
            pass
        
        return {
            "analysis_performed": True,
            "raw_analysis": response[:500]
        }
    
    def _calculate_deception_risk(self, greenwishing: Dict, greenhushing: Dict,
                                  selective: Dict, tunnel_vision: Dict) -> Dict[str, Any]:
        """Calculate overall deception risk score"""
        
        # Weighted average
        weights = {
            "greenwishing": 0.30,
            "greenhushing": 0.30,
            "selective_disclosure": 0.25,
            "carbon_tunnel_vision": 0.15
        }
        
        weighted_score = (
            greenwishing["score"] * weights["greenwishing"] +
            greenhushing["score"] * weights["greenhushing"] +
            selective["score"] * weights["selective_disclosure"] +
            (100 if tunnel_vision["detected"] else 0) * weights["carbon_tunnel_vision"]
        )
        
        # Determine level
        if weighted_score >= 60:
            level = "HIGH"
        elif weighted_score >= 35:
            level = "MODERATE"
        else:
            level = "LOW"
        
        # Identify primary concerns
        primary_concerns = []
        if greenwishing["detected"]:
            primary_concerns.append("Greenwishing - unfunded aspirational goals")
        if greenhushing["detected"]:
            primary_concerns.append("Greenhushing - incomplete ESG disclosure")
        if selective["detected"]:
            primary_concerns.append("Selective Disclosure - cherry-picked data")
        if tunnel_vision["detected"]:
            primary_concerns.append("Carbon Tunnel Vision - narrow ESG focus")
        
        return {
            "score": round(weighted_score, 1),
            "level": level,
            "primary_concerns": primary_concerns,
            "component_scores": {
                "greenwishing": greenwishing["score"],
                "greenhushing": greenhushing["score"],
                "selective_disclosure": selective["score"],
                "carbon_tunnel_vision": 100 if tunnel_vision["detected"] else 0
            }
        }
    
    def _generate_recommendations(self, deception_risk: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on detected deception tactics"""
        
        recommendations = []
        
        if deception_risk["score"] >= 50:
            recommendations.append("Request detailed implementation roadmap with CAPEX allocation for ESG commitments")
        
        if "Greenwishing" in str(deception_risk.get("primary_concerns", [])):
            recommendations.append("Require third-party validation of net-zero pathway and funding mechanisms")
            recommendations.append("Request Science Based Targets initiative (SBTi) validation")
        
        if "Greenhushing" in str(deception_risk.get("primary_concerns", [])):
            recommendations.append("Request complete BRSR/GRI/SASB disclosure across all material topics")
            recommendations.append("Verify against mandatory filing requirements (SEBI BRSR, CSRD, SEC)")
        
        if "Selective Disclosure" in str(deception_risk.get("primary_concerns", [])):
            recommendations.append("Request full organizational boundary disclosure including JVs and subsidiaries")
            recommendations.append("Verify baseline year selection rationale")
        
        if "Carbon Tunnel Vision" in str(deception_risk.get("primary_concerns", [])):
            recommendations.append("Request comprehensive ESG disclosure beyond carbon (water, waste, social, governance)")
            recommendations.append("Verify alignment with UN SDGs across all ESG pillars")
        
        if not recommendations:
            recommendations.append("Disclosure appears comprehensive - continue monitoring")
        
        return recommendations


# Global instance
greenwishing_detector = GreenwishingDetector()

def get_greenwishing_detector() -> GreenwishingDetector:
    """Get global greenwishing detector instance"""
    return greenwishing_detector
