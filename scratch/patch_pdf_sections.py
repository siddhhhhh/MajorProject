import os

with open('api/pdf_generator.py', 'r', encoding='utf-8') as f:
    text = f.read()

patch_pipeline_quality = """
    # === PIPELINE QUALITY & DATA INTEGRITY ===
    s += _sec("SECTION 2: PIPELINE QUALITY & DATA INTEGRITY")
    dq = raw.get("data_quality", {})
    if dq:
        s.append(_kvtbl([
            ["Reporting Currency", str(dq.get("reporting_currency", "Unknown"))],
            ["Data Freshness", f"Year {dq.get('data_freshness_year', 'Unknown')}"],
            ["Verified Source Count", str(dq.get("verified_source_count", 0))],
            ["Real Peer Count", str(dq.get("real_peer_count", 0))],
            ["Temporal Gap Found", "Yes" if dq.get("temporal_gap_found") else "No"]
        ]))
    else:
        s.append(Paragraph("No specific data quality metrics logged.", BD))
    s.append(SP)
"""

patch_claim_decomp = """
    # === ESG CLAIM DECOMPOSITION ===
    s += _sec("SECTION 7A: ESG CLAIM DECOMPOSITION")
    decomp = _get_agent(raw, "claim_decomposition")
    if decomp and decomp.get("sub_claims"):
        s.append(Paragraph("Sub-claims extracted:", BD))
        for sc in decomp.get("sub_claims", [])[:5]:
            s.append(Paragraph(f"  • [{sc.get('type','Claim')}] {sc.get('text','')}", BD))
        
        tensions = decomp.get("logical_tension_pairs", [])
        if tensions:
            s.append(SP)
            s.append(Paragraph("Logical Tension Pairs Found:", BD))
            for tp in tensions[:3]:
                s.append(Paragraph(f"  ⚠ {tp.get('tension_description','')}", WN))
    else:
        s.append(Paragraph("No detailed claim decomposition available.", BD))
    s.append(SP)
"""

patch_commitment = """
    # === COMMITMENT TIMELINE ===
    s += _sec("SECTION 11B: COMMITMENT TIMELINE")
    com_ledg = _get_agent(raw, "commitment_ledger_update")
    if not com_ledg:
        com_ledg = raw.get("commitment_ledger", {})
    if com_ledg and (com_ledg.get("inserted_commitments", 0) > 0 or com_ledg.get("revision_events")):
        s.append(Paragraph(f"Promise Degradation Score: {com_ledg.get('promise_degradation_score', 'N/A')}/100", BD))
        revs = com_ledg.get("revision_events", [])
        if revs:
            s.append(Paragraph(f"Revision Events Detected ({len(revs)}):", BD))
            for r in revs[:5]:
                s.append(Paragraph(f"  • {r.get('revision_date','')} [{r.get('revision_type','')}]: {r.get('explanation','')}", BD))
        else:
            s.append(Paragraph("No substantive weakening events detected.", BD))
    else:
        s.append(Paragraph("No ledger commitment revisions available for this run.", BD))
    s.append(SP)
"""

patch_kg = """
    # === KNOWLEDGE GRAPH HISTORY ===
    s += _sec("SECTION 11C: KNOWLEDGE GRAPH HISTORY")
    kg = raw.get("knowledge_graph_history", {})
    if kg:
        s.append(Paragraph(f"Fact count: {kg.get('fact_count', 0)}", BD))
        s.append(Paragraph(f"KPI history points: {kg.get('kpi_history_count', 0)}", BD))
        drift = kg.get("drift_score")
        if drift is not None:
            s.append(Paragraph(f"YoY Drift Score: {drift}/100", BD))
    else:
        s.append(Paragraph("No persistent Knowledge Graph history available.", BD))
    s.append(SP)
"""

patch_mismatch = """
    # === ESG MISMATCH DETECTOR ===
    s += _sec("SECTION 12: ESG MISMATCH DETECTOR")
    mis = raw.get("mismatch_detector", {})
    if mis:
        s.append(Paragraph(f"Mismatch Detected: {'Yes' if mis.get('mismatch_found') else 'No'}", BD))
        s.append(Paragraph(f"Summary: {mis.get('summary', 'N/A')}", BD))
        conflicts = mis.get("conflicting_points", [])
        for c in conflicts[:3]:
            s.append(Paragraph(f"  ⚠ {c.get('promised_metric','')} vs {c.get('actual_metric','')}", WN))
    else:
        s.append(Paragraph("No ESG mismatch signals detected.", BD))
    s.append(SP)
"""

# Insert PIPELINE QUALITY after EXECUTIVE SUMMARY
text = text.replace('    # === CLAIM BREAKDOWN ===', patch_pipeline_quality + '\n    # === CLAIM BREAKDOWN ===')

# Insert CLAIM DECOMP after CONTRADICTIONS
text = text.replace('    # === REGULATORY FRAMEWORK STATUS (FULL) ===', patch_claim_decomp + '\n    # === REGULATORY FRAMEWORK STATUS (FULL) ===')

# Insert COMMITMENT, KG, MISMATCH after APPENDIX C or before APPENDIX A
text = text.replace('    # === APPENDIX A ===', patch_commitment + patch_kg + patch_mismatch + '\n    # === APPENDIX A ===')

with open('api/pdf_generator.py', 'w', encoding='utf-8') as f:
    f.write(text)
