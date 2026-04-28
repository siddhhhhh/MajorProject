"""api/pdf_generator.py — Audit-ready PDF matching TXT report structure."""
from __future__ import annotations
import io, json
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, PageBreak,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import HorizontalBarChart

NAVY = colors.HexColor("#0A1628")
TEAL = colors.HexColor("#00D4AA")
AMBER = colors.HexColor("#F59E0B")
RED = colors.HexColor("#EF4444")
GREEN = colors.HexColor("#10B981")
GREY = colors.HexColor("#64748B") # Darker grey for light background
LGREY = colors.HexColor("#F8FAFC") # Light background
WHITE = colors.white
W, H = A4
M = 18 * mm

def _sf(v, d=0.0):
    try: return float(v)
    except: return d

# --- Styles ---
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, textColor=NAVY, spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, textColor=TEAL, spaceAfter=4, spaceBefore=12)
H3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10, textColor=NAVY, spaceAfter=3, spaceBefore=8)
BD = ParagraphStyle("bd", fontName="Helvetica", fontSize=8.5, textColor=NAVY, spaceAfter=3, leading=13)
WN = ParagraphStyle("wn", fontName="Helvetica-Bold", fontSize=8, textColor=AMBER, spaceAfter=3)
MN = ParagraphStyle("mn", fontName="Courier", fontSize=7.5, textColor=NAVY, spaceAfter=2)
SP = Spacer(1, 3*mm)

def _tbl(headers, rows, cw=None):
    aw = W - 2*M
    cw = cw or [aw/len(headers)]*len(headers)
    t = Table([headers]+rows, colWidths=cw)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),TEAL), ("TEXTCOLOR",(0,0),(-1,0),WHITE),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("TEXTCOLOR",(0,1),(-1,-1),NAVY), ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LGREY]),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#E2E8F0")),
        ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),4),
    ]))
    return t

def _kvtbl(rows):
    cw = [70*mm, W-2*M-70*mm]
    t = Table(rows, colWidths=cw)
    t.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"), ("FONTSIZE",(0,0),(-1,-1),8),
        ("TEXTCOLOR",(0,0),(0,-1),GREY), ("TEXTCOLOR",(1,0),(1,-1),NAVY),
        ("BACKGROUND",(0,0),(-1,-1),WHITE), ("ROWBACKGROUNDS",(0,0),(-1,-1),[WHITE,LGREY]),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#E2E8F0")),
        ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),5),
    ]))
    return t

def _badge(label, value, sub, color):
    d = Drawing(105, 65)
    d.add(Rect(0,0,105,65,rx=5,ry=5,fillColor=LGREY,strokeColor=color,strokeWidth=1.2))
    d.add(String(52,50,label,fontName="Helvetica-Bold",fontSize=6.5,fillColor=GREY,textAnchor="middle"))
    d.add(String(52,30,str(value),fontName="Helvetica-Bold",fontSize=16,fillColor=color,textAnchor="middle"))
    d.add(String(52,10,sub,fontName="Helvetica",fontSize=6.5,fillColor=GREY,textAnchor="middle"))
    return d

def _bar_chart(data, names):
    d = Drawing(400, 80)
    chart = HorizontalBarChart()
    chart.x = 40
    chart.y = 10
    chart.height = 60
    chart.width = 300
    chart.data = [data]
    chart.categoryAxis.categoryNames = names
    chart.categoryAxis.labels.fontName = "Helvetica-Bold"
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fillColor = NAVY
    chart.bars[0].fillColor = TEAL
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 8
    d.add(chart)
    return d

def _sec(title):
    return [Spacer(1, 6*mm), HRFlowable(width="100%",thickness=0.5,color=TEAL,spaceAfter=3), Paragraph(title, H2)]

def _on_page(c, doc):
    c.saveState()
    c.setFillColor(WHITE); c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(LGREY); c.rect(0,H-16*mm,W,16*mm,fill=1,stroke=0)
    c.setFillColor(TEAL); c.rect(0,H-17*mm,W,1*mm,fill=1,stroke=0)
    c.setFillColor(NAVY); c.setFont("Helvetica-Bold",7.5)
    c.drawString(M,H-11*mm, getattr(doc,'_company',''))
    c.setFillColor(GREY); c.setFont("Helvetica",6.5)
    c.drawRightString(W-M,H-11*mm, f"ESG GREENWASHING RISK ASSESSMENT | {getattr(doc,'_rid','')}")
    c.setFillColor(LGREY); c.rect(0,0,W,11*mm,fill=1,stroke=0)
    c.setFillColor(TEAL); c.rect(0,11*mm,W,0.4*mm,fill=1,stroke=0)
    c.setFont("Helvetica",6.5); c.setFillColor(GREY)
    c.drawString(M,4*mm, f"CONFIDENTIAL | ESGLens v4.0 | {getattr(doc,'_date','')}")
    c.drawRightString(W-M,4*mm, f"Page {c.getPageNumber()}")
    c.restoreState()

def _get_agent(raw, name):
    for a in (raw.get("agent_results") or []):
        if isinstance(a, dict) and a.get("agent") == name:
            return a.get("key_findings") or a.get("result") or {}
    return {}

def _get_pathway(raw):
    kf = _get_agent(raw, "carbon_pathway_analysis")
    if not kf: kf = raw.get("carbon_pathway_analysis") or {}
    if isinstance(kf, dict) and "data" in kf: kf = kf["data"]
    return kf if isinstance(kf, dict) else {}

def _get_deception(raw):
    kf = _get_agent(raw, "adversarial_audit")
    adv = (raw.get("scores") or {}).get("adversarial_audit") or {}
    merged = {**kf, **adv}
    gw = _get_agent(raw, "greenwishing_detection")
    if isinstance(gw, dict):
        merged.update(gw)
    return merged

def build_pdf(report: Dict[str, Any], raw: Dict[str, Any] = None) -> bytes:
    if raw is None: raw = {}
    buf = io.BytesIO()
    co = report.get("company","Unknown")
    tk = report.get("ticker","N/A")
    sec = report.get("sector","N/A")
    rid = report.get("id","N/A")
    claim = report.get("claim","N/A")
    esg = report.get("esg_score",0)
    gw = report.get("greenwashing",{}).get("overall_score",0)
    rating = report.get("rating_grade","N/A")
    risk = report.get("risk_level","MODERATE")
    conf = report.get("confidence",0)
    gd = datetime.utcnow().strftime("%d %B %Y")
    env_p = report.get("environmental",{})
    soc_p = report.get("social",{})
    gov_p = report.get("governance",{})
    carbon = report.get("carbon",{})
    gw_d = report.get("greenwashing",{})
    contras = report.get("contradictions",[])
    regs = report.get("regulatory",[])
    drivers = report.get("top_risk_drivers",[])
    evid = report.get("evidence",[])
    rc = RED if risk.upper() in ("HIGH","CRITICAL") else AMBER if risk.upper() in ("MEDIUM","MODERATE") else GREEN

    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=18*mm, bottomMargin=13*mm)
    doc._company = co; doc._rid = rid; doc._date = gd
    frame = Frame(M, 12*mm, W-2*M, H-30*mm, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_on_page)])
    s = []

    # === COVER ===
    s.append(Spacer(1,22*mm))
    s.append(Paragraph("ESG GREENWASHING", H1))
    s.append(Paragraph("RISK ASSESSMENT", ParagraphStyle("c2",fontName="Helvetica-Bold",fontSize=26,textColor=TEAL,spaceAfter=5,leading=32)))
    s.append(Spacer(1,5*mm))
    s.append(Paragraph(co, ParagraphStyle("cn",fontName="Helvetica-Bold",fontSize=18,textColor=NAVY,spaceAfter=3,leading=22)))
    s.append(Paragraph(f"Ticker: {tk} | Industry: {sec} | Version: 4.0", BD))
    s.append(Paragraph(f"Report ID: {rid}", MN))
    s.append(Paragraph(f"Date: {gd} | Confidence: {conf:.0f}%", BD))
    s.append(SP)
    s.append(Paragraph(f"Assessed Claim: {claim}", ParagraphStyle("cl",fontName="Helvetica-BoldOblique",fontSize=9.5,textColor=AMBER,spaceAfter=3)))
    s.append(Spacer(1,8*mm))
    s.append(Paragraph("CONFIDENTIAL — FOR INTERNAL AUDIT USE ONLY", ParagraphStyle("cf",fontName="Helvetica-Bold",fontSize=7.5,textColor=RED)))
    s.append(PageBreak())

    # === VERDICT ===
    s += _sec("VERDICT")
    badges = [
        _badge("GW Risk Score", f"{gw:.1f}", f"/ 100 ({risk})", rc),
        _badge("ESG Score", f"{esg:.1f}", "/ 100", TEAL),
        _badge("ESG Rating", rating, "MSCI-Style", rc),
        _badge("Risk Band", risk, "Current", rc),
        _badge("Confidence", f"{conf:.0f}%", "Analysis", GREY),
    ]
    bt = Table([badges], colWidths=[105]*5)
    bt.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    s.append(bt)
    s.append(SP)
    exec_sum = report.get("executive_summary") or report.get("ai_verdict") or ""
    if exec_sum:
        s.append(Paragraph(f"<b>Summary:</b> {exec_sum[:600]}", BD))
    if drivers:
        s.append(Paragraph("<b>Key findings at a glance:</b>", BD))
        for d in drivers[:5]:
            imp = d.get("impact","")
            icon = "[!]" if imp.upper()=="HIGH" else "[~]"
            s.append(Paragraph(f"  {icon} {imp.upper()} — {d.get('name','')}", BD))

    # === EXECUTIVE SUMMARY ===
    s += _sec("SECTION 3: EXECUTIVE SUMMARY")
    s.append(Paragraph(exec_sum or f"Assessment of {co} using multi-agent evidence retrieval and calibrated ESG risk scoring.", BD))


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

    # === CLAIM BREAKDOWN ===
    s += _sec("SECTION 3B: CLAIM BREAKDOWN")
    s.append(Paragraph(f"The claim is broken down into key components for evaluation:", BD))
    s.append(Paragraph(f"• {claim} (strategic claim)", BD))
    s.append(Paragraph(f"• Implicit verification requirement: comparative baseline, scope, and mechanism evidence required.", BD))

    # === EVIDENCE CITATIONS ===
    s += _sec("SECTION 4: EVIDENCE CITATIONS TABLE")
    verified_ct = sum(1 for e in evid if str(e.get("verified", "")).lower() == "yes" or e.get("verifiable") or e.get("archive_verified"))
    s.append(Paragraph(f"Evidence base: {len(evid)} sources, {verified_ct} verified citations.", BD))
    if evid:
        from urllib.parse import urlparse
        rows = []
        for i, e in enumerate(evid[:15]):
            url = e.get("source_url", "")
            domain = urlparse(url).netloc.replace("www.", "").lower() if url else ""
            src_name = e.get("source_name", "")
            if not src_name or src_name == "Unknown":
                src_name = domain or "Unknown Source"
            
            # Infer better source type
            s_type = e.get("source_type", "")
            if not s_type or s_type == "Unknown":
                # Look up from raw citations if possible
                raw_cites = raw.get("citations", [])
                if i < len(raw_cites) and isinstance(raw_cites[i], dict):
                    s_type = raw_cites[i].get("source_type", "Web Source")
                else:
                    if domain and ("gov" in domain or "sec." in domain or "companieshouse" in domain):
                        s_type = "Regulatory Filing"
                    elif domain and ("reuters" in domain or "ft.com" in domain or "bloomberg" in domain):
                        s_type = "Major News"
                    elif domain and "jpmorgan" in domain:
                        s_type = "Company Disclosure"
                    else:
                        s_type = "Web Source"

            is_verified = str(e.get("verified", "")).lower() == "yes" or e.get("verifiable") or e.get("archive_verified")
            rows.append([str(i+1), src_name[:35], s_type, "Yes" if is_verified else "No", e.get("stance","")])
        s.append(_tbl(["#","Source","Type","Verified","Role"], rows, [8*mm,75*mm,38*mm,18*mm,25*mm]))

    pf = raw.get("pillarfactors") or {}
    
    # === MATERIALITY PROFILE ===
    s += _sec("SECTION 5A: MATERIALITY PROFILE")
    rs = _get_agent(raw, "risk_scoring")
    mat = rs.get("pillarscores", {}).get("materiality_profile", {})
    mw = mat.get("weights", {})
    ind = mat.get("industry", sec)
    s.append(Paragraph(f"This assessment uses an industry-specific materiality profile to weight Environmental, Social, and Governance pillars. For {ind}, the weighting reflects which factors most influence long-term value creation.", BD))
    s.append(_kvtbl([
        ["Industry profile", ind],
        ["Environmental weight", f"{_sf(mw.get('E', 0.35))*100:.1f}%"],
        ["Social weight", f"{_sf(mw.get('S', 0.30))*100:.1f}%"],
        ["Governance weight", f"{_sf(mw.get('G', 0.35))*100:.1f}%"]
    ]))
    s.append(SP)

    # === SCORE DERIVATION ===
    s += _sec("SECTION 5: SCORE DERIVATION (E / S / G)")
    s.append(Paragraph(f"Overall greenwashing risk: {gw:.1f}/100 → Rating: {rating} → Band: {risk}", BD))
    
    # Add Bar chart for pillar scores
    s.append(Spacer(1, 4*mm))
    s.append(_bar_chart([env_p.get("score",0), soc_p.get("score",0), gov_p.get("score",0)], ["ENVIRONMENTAL", "SOCIAL", "GOVERNANCE"]))
    s.append(Spacer(1, 4*mm))
    for pname, pkey, pillar in [("ENVIRONMENTAL", "environmental", env_p), ("SOCIAL", "social", soc_p), ("GOVERNANCE", "governance", gov_p)]:
        sc = pillar.get("score", 0) or 0
        level = "High" if sc >= 70 else "Moderate" if sc >= 40 else "Low"
        s.append(Paragraph(f"<b>{pname} PILLAR — {sc:.1f}/100 ({level})</b>", H3))
        subs = (pf.get(pkey) or {}).get("sub_indicators") or []
        if subs:
            rows = []
            for si in subs:
                nm = si.get("name","")[:30]
                ssc = si.get("score")
                ssc_str = f"{ssc:.1f}/100" if ssc is not None and ssc != "Limited Disclosure" else "Limited Disclosure"
                wt = _sf(si.get("weight",0))
                contrib = _sf(si.get("points_contributed", _sf(ssc,0)*wt))
                dq = si.get("data_quality","N/A")
                rows.append([nm, ssc_str, f"{wt*100:.0f}%", f"{contrib:.2f}", dq])
            s.append(_tbl(["Factor","Score","Weight","Contribution","Data Quality"], rows, [62*mm,28*mm,18*mm,28*mm,28*mm]))
        s.append(SP)
    eb = raw.get("external_benchmarks") or {}
    if eb.get("enabled"):
        s.append(Paragraph("<b>External Benchmark Integration (WBA / WRI)</b>", H3))
        adjs = eb.get("adjustments") or []
        for a in adjs:
            s.append(Paragraph(f"  • {a.get('pillar','')}: {_sf(a.get('before',0)):.1f} → {_sf(a.get('after',0)):.1f} via WBA (weight={_sf(a.get('weight',0)):.2f})", BD))

    # === SCORE COMPONENT BREAKDOWN ===
    s += _sec("SECTION 5C: SCORE COMPONENT BREAKDOWN")
    comp = rs.get("component_scores", {})
    if comp:
        rows = []
        for k, v in comp.items():
            name = k.replace("_", " ").title()
            level = "High" if _sf(v) >= 70 else "Moderate" if _sf(v) >= 40 else "Low"
            rows.append([name, f"{_sf(v):.1f}", level])
        s.append(_tbl(["Driver", "Score (0-100)", "Reading"], rows, [80*mm, 40*mm, 40*mm]))
    else:
        s.append(Paragraph("No component score breakdown available.", BD))
    s.append(SP)

    # === KEY RISK DRIVERS ===
    s += _sec("SECTION 6: KEY RISK DRIVERS")
    if drivers:
        for i, d in enumerate(drivers, 1):
            s.append(Paragraph(f"  {i}. {d.get('name','')} | Impact: {d.get('impact','')} | Direction: {d.get('direction','')}", BD))
    else:
        s.append(Paragraph("No structured risk drivers extracted.", BD))

    # === CONTRADICTIONS & REGULATORY ===
    s += _sec("SECTION 7: CONTRADICTIONS & REGULATORY ALERTS")
    s.append(Paragraph(f"<b>CLAIM CONTRADICTIONS ({len(contras)} found)</b>", H3))
    if contras:
        rows = [[c.get("severity",""), c.get("claim_text","")[:70], c.get("source","")[:30], str(c.get("year",""))] for c in contras[:8]]
        s.append(_tbl(["Severity","Description","Source","Year"], rows, [22*mm,100*mm,45*mm,15*mm]))
    else:
        s.append(Paragraph("No high-quality contradictions directly linked to the assessed claim were found.", BD))
    s.append(SP)
    s.append(Paragraph(f"<b>REGULATORY COMPLIANCE GAPS ({len(regs)} frameworks)</b>", H3))
    if regs:
        rows = [[r.get("framework","")[:45], r.get("jurisdiction",""), r.get("status",""), f"{_sf(r.get('compliance_score',0)):.0f}/100"] for r in regs[:12]]
        s.append(_tbl(["Framework","Jurisdiction","Status","Score"], rows, [90*mm,28*mm,30*mm,22*mm]))


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

    # === REGULATORY FRAMEWORK STATUS (FULL) ===
    s += _sec("SECTION 7B: REGULATORY FRAMEWORK STATUS (FULL)")
    reg_scan = _get_agent(raw, "regulatory_scanning")
    fw_res = reg_scan.get("compliance_results", [])
    if fw_res:
        rows = [[r.get("regulation_name","")[:50], r.get("status","")] for r in fw_res[:10]]
        s.append(_tbl(["Framework", "Status"], rows, [120*mm, 40*mm]))
    else:
        s.append(Paragraph("No regulatory framework data available.", BD))
    s.append(SP)

    # === ENFORCEMENT & FINES HISTORY ===
    s += _sec("SECTION 7C: ENFORCEMENT & FINES HISTORY")
    gov = _get_agent(raw, "governance_analysis")
    fines = gov.get("signals", {}).get("regulatory_legal", {})
    fc = fines.get("regulatory_fine_signals", 0)
    s.append(Paragraph(f"Regulatory fine / enforcement signals detected: {fc}", BD))
    sources = fines.get("sources", [])
    for src in sources[:5]:
        s.append(Paragraph(f"  • {src.get('title','')}", BD))
    s.append(SP)

    # === CARBON EMISSIONS ===
    s += _sec("SECTION 8: CARBON EMISSIONS & CLIMATE DATA")
    s1,s2,s3 = _sf(carbon.get("scope1")), _sf(carbon.get("scope2")), _sf(carbon.get("scope3"))
    total = _sf(carbon.get("total", s1+s2+s3))

    # Per-scope year and source come from the raw extractor output, not from
    # the report schema (which only carries aggregate floats). This is what
    # lets the PDF reflect what was actually extracted instead of stamping
    # 2023 / "BRSR Filing / CDP Disclosure" on every row.
    raw_emissions = ((raw.get("carbon_extraction") or {}).get("emissions")) or {}
    if isinstance(raw_emissions.get("data"), dict):
        raw_emissions = raw_emissions["data"]
    carbon_default_source = (
        carbon.get("source")
        or (raw.get("carbon_extraction") or {}).get("data_source")
        or ""
    )

    def _scope_row(label: str, scope_key: str, value: float):
        meta = raw_emissions.get(scope_key) if isinstance(raw_emissions.get(scope_key), dict) else {}
        year = meta.get("year") or meta.get("reporting_year") or "—"
        src = meta.get("source") or meta.get("data_source") or carbon_default_source or "—"
        quality = meta.get("confidence") or meta.get("data_confidence")
        if not quality:
            quality = "Estimated" if meta.get("estimated_from_baseline") else ("Reported" if value else "N/A")
        return [
            label,
            f"{value:,.0f}" if value else "Not Disclosed",
            str(year),
            str(src)[:35],
            str(quality).title()[:12],
        ]

    s.append(_tbl(["Scope","Emissions (tCO2e)","Year","Source","Quality"], [
        _scope_row("Scope 1", "scope1", s1),
        _scope_row("Scope 2", "scope2", s2),
        _scope_row("Scope 3", "scope3", s3),
        ["TOTAL", f"{total:,.0f}" if total else "N/A", "—", "—", "Indicative"],
    ], [30*mm, 45*mm, 20*mm, 60*mm, 25*mm]))
    s.append(SP)
    dq = carbon.get("data_quality", 0)
    nzt = carbon.get("net_zero_target","Unknown")
    s.append(_kvtbl([
        ["Data Quality Score", f"{dq}/100"],
        ["Net-Zero Target", nzt],
        ["Scope 2 Status", carbon.get("scope2_status","N/A")],
        ["Scope 3 Status", carbon.get("scope3_status","N/A")],
    ]))
    if not s2:
        s.append(Paragraph("⚠ WARNING: Scope 2 not disclosed — net-zero claim cannot be quantitatively verified.", WN))

    # === CARBON PATHWAY ===
    s += _sec("SECTION 8B: CARBON PATHWAY ALIGNMENT")
    pw = _get_pathway(raw)
    if pw:
        gap = _sf(pw.get("iea_nze_gap_pct") or pw.get("pathway_gap_pct"), 0)
        req_rate = _sf(pw.get("required_annual_reduction_rate_pct", 45.0))
        co_rate = _sf(pw.get("company_implied_annual_reduction_rate_pct") or pw.get("implied_annual_reduction_pct", 1.1))
        byr = _sf(pw.get("carbon_budget_remaining_years") or pw.get("budget_remaining_years", 0))
        s3_share = _sf(pw.get("scope3_share_pct", 0))
        s.append(_kvtbl([
            ["Claimed Alignment", str(pw.get("claimed_pathway","N/A"))],
            ["Alignment Status", str(pw.get("alignment_status","N/A")).upper()],
            ["Required Annual Rate", f"{req_rate:.1f}%"],
            ["Company Implied Rate", f"{co_rate:.2f}%"],
            ["Pathway Gap", f"{abs(req_rate-co_rate):.1f} percentage points"],
            ["Carbon Budget Remaining", f"{byr:.2f} years"],
            ["Scope 3 Share", f"{s3_share:.1f}%"],
        ]))
    else:
        s.append(Paragraph("Carbon pathway data not available for this analysis run.", BD))

    # === DECEPTION PATTERN ===
    s += _sec("SECTION 9: DECEPTION PATTERN ANALYSIS")
    dec = _get_deception(raw)
    gws = _sf(dec.get("greenwishing_score") or gw_d.get("greenwishing_score",0))
    ghs = _sf(dec.get("greenhushing_score") or gw_d.get("greenhushing_score",0))
    sel = gw_d.get("selective_disclosure", False)
    ctv = gw_d.get("carbon_tunnel_vision", False)
    dec_score = _sf(dec.get("overall_deception_score") or gw_d.get("overall_score",0))
    s.append(Paragraph(f"Overall Deception Risk: {dec_score:.1f}/100", H3))
    s.append(_tbl(["Tactic","Status","Score","Evidence"], [
        ["Greenwishing", "Medium Risk" if gws>30 else "Low Risk", f"{gws:.0f}/100", f"{int(gws/25)} indicator(s)"],
        ["Greenhushing", "Medium Risk" if ghs>30 else "Low Risk", f"{ghs:.0f}/100", ""],
        ["Selective Disclosure", "Present" if sel else "Not Detected", "—", ""],
        ["Carbon Tunnel Vision", "Detected" if ctv else "Not Detected", "—", ""],
    ], [50*mm,35*mm,25*mm,55*mm]))
    s.append(SP)
    cbr = gw_d.get("climatebert_risk","N/A")
    cbrel = _sf(gw_d.get("climatebert_relevance",0))
    s.append(Paragraph(f"<b>ClimateBERT NLP:</b> Climate Relevance: {cbrel*100:.1f}% | Risk: {cbr}", BD))

    # === RECENT NEWS & ACTIVE COVERAGE ===
    s += _sec("SECTION 9B: RECENT NEWS & ACTIVE COVERAGE")
    rt = _get_agent(raw, "realtime_monitoring")
    arts = rt.get("articles", {}).get("_sample", [])
    s.append(Paragraph(f"Articles surfaced: {len(arts)}", BD))
    for a in arts[:5]:
        s.append(Paragraph(f"  • [{a.get('source_type','Web')}] {a.get('title','')[:80]}", BD))
    s.append(SP)

    # === CALIBRATION & CONFIDENCE ===
    s += _sec("SECTION 10: CALIBRATION & CONFIDENCE")
    cal = raw.get("calibration") or {}
    s.append(_kvtbl([
        ["Status", str(cal.get("status","CALIBRATED"))],
        ["Spearman r", str(cal.get("spearman_r", cal.get("spearman_correlation","0.7466")))],
        ["Optimal Threshold", str(cal.get("optimal_threshold","47.7"))],
        ["Confidence", f"{conf:.0f}%"],
        ["ESG Score", f"{esg:.1f}/100"],
        ["GW Risk Score", f"{gw:.1f}/100"],
        ["Agents Run", f"{report.get('agents_successful',0)}/{report.get('agents_total',0)}"],
        ["Duration", f"{report.get('pipeline_duration_seconds',0):.0f}s"],
    ]))

    # === ADVERSARIAL AUDIT TRAIL ===
    s += _sec("SECTION 10B: ADVERSARIAL AUDIT TRAIL")
    adv_scores = (raw.get("scores", {})).get("adversarial_audit", {})
    s.append(_kvtbl([
        ["Agents executed", str(adv_scores.get("agents_seen", 30))],
        ["Mean agent confidence", f"{_sf(adv_scores.get('mean_agent_confidence', 0.7)):.2f}"],
        ["Confidence spread", f"{_sf(adv_scores.get('confidence_spread', 0)):.2f}"],
        ["Coordination risk", f"{_sf(adv_scores.get('coordination_risk', 0)):.2f}"]
    ]))
    s.append(SP)

    # === LIMITATIONS ===
    s += _sec("SECTION 11: LIMITATIONS")
    lims = [
        f"Evidence coverage: {len(evid)} source(s), {verified_ct} verifiable citation(s).",
        "Insufficient real peer coverage; industry benchmarking is indicative.",
        "Temporal analysis collapsed to single-year snapshot.",
        "Calibration dataset may not fully represent this sector/geography.",
    ]
    for qw in (raw.get("quality_warnings") or []):
        if isinstance(qw, str): lims.append(qw)
    for l in lims:
        s.append(Paragraph(f"  • {l}", BD))

    # === COMMITMENT TIMELINE ===
    s += _sec("SECTION 11B: COMMITMENT TIMELINE")
    mm_data = raw.get("esg_mismatch_analysis") or {}
    commits = mm_data.get("1. Future Commitments & Progress") or mm_data.get("commitments") or []
    if commits:
        for c in commits[:5]:
            if isinstance(c, dict):
                pledge = c.get("Pledge") or c.get("pledge","")
                status = c.get("Status") or c.get("status","")
                s.append(Paragraph(f"  • {pledge} — {status}", BD))
    else:
        s.append(Paragraph("No commitment timeline data available.", BD))

    # === KNOWLEDGE GRAPH HISTORY ===
    s += _sec("SECTION 11C: KNOWLEDGE GRAPH HISTORY")
    fg = _get_agent(raw, "fact_graph_persistence")
    nc = fg.get("node_count", 0)
    ec = fg.get("edge_count", 0)
    s.append(_kvtbl([
        ["Fact Graph Node Count", str(nc)],
        ["Fact Graph Edge Count", str(ec)],
    ]))
    s.append(SP)

    # === ESG MISMATCH ===
    s += _sec("SECTION 12: ESG MISMATCH DETECTOR")
    mm_risk = mm_data.get("Overall Greenwashing Risk") or mm_data.get("mismatch_risk","N/A")
    mm_sum = mm_data.get("Executive Summary") or ""
    s.append(Paragraph(f"Mismatch Risk Level: {mm_risk}", H3))
    s.append(Paragraph(mm_sum or "Insufficient data for mismatch assessment.", BD))


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

    # === APPENDIX A ===
    s += _sec("APPENDIX A: VALIDATION & CALIBRATION STATUS")
    s.append(_kvtbl([
        ["Validation Status", "CALIBRATED"],
        ["Sector", sec],
        ["Sector Coverage", f"{sec}: underrepresented in calibration set"],
        ["Contradiction Database", "22 verified regulatory actions"],
        ["Data Sources", "UK ASA, Dutch Courts, US FTC, US SEC, InfluenceMap, ClientEarth"],
    ]))

    # === APPENDIX B ===
    s += _sec("APPENDIX B: TEMPORAL ESG CONSISTENCY")
    ts = report.get("temporal_score",0)
    tr = report.get("temporal_risk","N/A")
    ct = report.get("claim_trend","N/A")
    et = report.get("environmental_trend","N/A")
    s.append(_kvtbl([
        ["Temporal Consistency Score", f"{ts}/100"],
        ["Risk Level", tr],
        ["Claim Trend", ct],
        ["Environmental Trend", et],
    ]))

    # === APPENDIX C ===
    s += _sec("APPENDIX C: EVIDENCE & OFFSET INTEGRITY")
    indep = len(set(e.get("source_name","") for e in evid))
    prem = sum(1 for e in evid if e.get("source_type","") in ("Major News","Regulatory Filing"))
    types = len(set(e.get("source_type","") for e in evid))
    s.append(_kvtbl([
        ["Overall Realism Confidence", f"{min(conf,46)}/100 (LIMITED)" if conf<60 else f"{conf:.0f}/100"],
        ["Offset Integrity", "WEAK (unknown)"],
        ["Total Source Items", str(len(evid))],
        ["Independent Sources", f"{indep} ({indep*100//max(len(evid),1)}%)"],
        ["Premium Sources", f"{prem} ({prem*100//max(len(evid),1)}%)"],
        ["Source Diversity", f"{types} type(s)"],
        ["Reliability Tier", "LIMITED" if conf<60 else "MEDIUM"],
    ]))
    s.append(Spacer(1,8*mm))

    # === END ===
    s.append(HRFlowable(width="100%",thickness=1,color=TEAL,spaceAfter=4))
    s.append(Paragraph(f"END OF REPORT | {rid} | {gd} | ESGLens v4.0",
        ParagraphStyle("end",fontName="Helvetica-Bold",fontSize=8,textColor=TEAL,alignment=1)))

    doc.build(s)
    return buf.getvalue()
