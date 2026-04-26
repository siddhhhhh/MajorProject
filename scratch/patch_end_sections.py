import re

path = r'c:\Users\Mahi\major\core\professional_report_generator.py'
with open(path, encoding='utf-8') as f:
    content = f.read()

# 1. Section 10: Calibration & Confidence
s10_old = 'section9 = [major, "SECTION 10: CALIBRATION & CONFIDENCE", major]'
s10_new = '''section9 = [major, "SECTION 10: CALIBRATION & CONFIDENCE", major]
        section9.append(self._wrap_paragraph("This score is calibrated against a limited sample of verified cases. Results are indicative but should be interpreted with caution.", width=80))
        section9.append("")'''
content = content.replace(s10_old, s10_new)

# 2. Section 11: Limitations
lim_old = '''        for lim in v["limitations"] if isinstance(v["limitations"], list) else []:
            txt = str(lim).strip()'''
lim_new = '''        for lim in v["limitations"] if isinstance(v["limitations"], list) else []:
            txt = str(lim).strip()
            txt = txt.replace("agent failed or returned no output", "some analytical dimensions were not available for this run")
            txt = txt.replace("Agent failed or returned no output", "Some analytical dimensions were not available for this run")
            txt = txt.replace("failed or returned no output", "was not available for this run")'''
content = content.replace(lim_old, lim_new)

# 3. Section 11B: Commitment Timeline
s11b_old = 'section10b = [major, "SECTION 11B: COMMITMENT TIMELINE", major]'
s11b_new = '''section10b = [major, "SECTION 11B: COMMITMENT TIMELINE", major]
        section10b.append("This section tracks how company commitments evolve over time and whether accountability weakens.")
        section10b.append("")'''
content = content.replace(s11b_old, s11b_new)

s11b_score_old = '''section10b.append(f"Promise Degradation Score: {commitment.get('promise_degradation_score', 'N/A')}/100")'''
s11b_score_new = '''section10b.append(f"Promise Degradation Score: {commitment.get('promise_degradation_score', 'N/A')}/100 (Higher score indicates greater backsliding)")'''
content = content.replace(s11b_score_old, s11b_score_new)

# 4. Section 12: ESG Mismatch Detector
s12_ev_old = '''evidence = str(item.get("Evidence Source") or item.get("evidence_source") or "N/A").strip()'''
s12_ev_new = '''evidence = str(item.get("Evidence Source") or item.get("evidence_source") or "N/A").strip()
                if evidence.startswith("http"):
                    import urllib.parse
                    try:
                        domain = urllib.parse.urlparse(evidence).netloc.replace("www.", "")
                        evidence = f"Source: {domain}"
                    except Exception:
                        pass
                elif len(evidence) > 60:
                    evidence = evidence[:57] + "..."'''
content = content.replace(s12_ev_old, s12_ev_new)

# 5. Appendix A: Validation & Calibration
appA_old = '''        lines = [
            "VALIDATION & CALIBRATION STATUS",
            "─" * 52,
        ]'''
appA_new = '''        lines = [
            "VALIDATION & CALIBRATION STATUS",
            "─" * 52,
            "This appendix summarizes validation coverage and calibration reliability.",
        ]'''
content = content.replace(appA_old, appA_new)

# 6. Appendix B: Temporal Consistency
# Fix "moderate inconsistency detected" when inconsistency_detected is False.
# Risk level is printed. If risk_level == "MODERATE" and not inconsistency_detected, let's just make risk_level "LOW" or "N/A".
appB_old = '''        temporal_score = temporal_result.get("temporal_consistency_score", 50)
        risk_level = temporal_result.get("risk_level", "MODERATE")
        claim_trend = temporal_result.get("claim_trend", "unknown")
        env_trend = temporal_result.get("environmental_trend", "unknown")
        inconsistency_detected = temporal_result.get("temporal_inconsistency_detected", False)'''
appB_new = '''        temporal_score = temporal_result.get("temporal_consistency_score", 50)
        risk_level = temporal_result.get("risk_level", "MODERATE")
        claim_trend = temporal_result.get("claim_trend", "unknown")
        env_trend = temporal_result.get("environmental_trend", "unknown")
        inconsistency_detected = temporal_result.get("temporal_inconsistency_detected", False)
        
        if not inconsistency_detected and risk_level.upper() in ["MODERATE", "MEDIUM"]:
            risk_level = "LOW (No material inconsistencies found)"'''
content = content.replace(appB_old, appB_new)

# 7. Appendix C: Evidence & Offset Integrity
appC_old = '''Overall Realism Confidence: {diagnostics.get('realism_score', 0)}/100 ({str(diagnostics.get('realism_label', 'unknown')).upper()})

Offset Integrity:
  - Classification: {str(diagnostics.get('offset_integrity', 'unknown')).upper()} ({diagnostics.get('offset_status', 'unknown')})
  - Penalty Applied: {diagnostics.get('offset_penalty', 0)} point(s)

Evidence Composition:
  - Total Source Items: {evidence_diag.get('total_evidence_sources', 0)}
  - Independent Sources: {evidence_diag.get('independent_sources', 0)} ({evidence_diag.get('independent_share_pct', 0)}%)
  - Premium Sources: {evidence_diag.get('premium_sources', 0)} ({evidence_diag.get('premium_share_pct', 0)}%)
  - Source Diversity: {evidence_diag.get('source_diversity', 0)} type(s)
  - Evidence Gap Flag: {'YES' if evidence_diag.get('evidence_gap') else 'NO'}

Temporal Reliability:
  - Mode: {temporal_diag.get('mode', 'none')}
  - Weight in Final Scoring: {temporal_diag.get('weight', 0)}
  - Data Quality: {temporal_diag.get('quality_score', 0)}/100 ({temporal_diag.get('quality_label', 'unknown')})
  - Reliability Tier: {str(temporal_diag.get('reliability', 'limited')).upper()}'''

appC_new = '''Overall Realism Confidence: {"Not available" if diagnostics.get('realism_score', 0) == 0 and diagnostics.get('realism_label', 'unknown') == 'unknown' else f"{diagnostics.get('realism_score', 0)}/100 ({str(diagnostics.get('realism_label', 'unknown')).upper()})"}

Offset Integrity:
  - Classification: {str(diagnostics.get('offset_integrity', 'unknown')).upper()} ({diagnostics.get('offset_status', 'unknown')})
  - Penalty Applied: {diagnostics.get('offset_penalty', 0)} point(s)

Evidence Composition:
  - Total Source Items: {evidence_diag.get('total_evidence_sources', 0)}
  - Independent Sources: {evidence_diag.get('independent_sources', 0)} ({evidence_diag.get('independent_share_pct', 0)}%)
  - Premium Sources: {evidence_diag.get('premium_sources', 0)} ({evidence_diag.get('premium_share_pct', 0)}%)
  - Source Diversity: {evidence_diag.get('source_diversity', 0)} type(s)
  - Evidence Gap Flag: {'YES' if evidence_diag.get('evidence_gap') else 'NO'}

Temporal Reliability:
  - Mode: {temporal_diag.get('mode', 'none')}
  - Weight in Final Scoring: {temporal_diag.get('weight', 0)}
  - Data Quality: {"Not available" if temporal_diag.get('quality_score', 0) == 0 and str(temporal_diag.get('quality_label', 'unknown')).lower() == 'unknown' else f"{temporal_diag.get('quality_score', 0)}/100 ({temporal_diag.get('quality_label', 'unknown')})"}
  - Reliability Tier: {str(temporal_diag.get('reliability', 'limited')).upper()}'''
content = content.replace(appC_old, appC_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patcher executed successfully")
