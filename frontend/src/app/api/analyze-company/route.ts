import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const { company_name, claim, industry } = await req.json();

    if (!company_name || !claim) {
      return NextResponse.json({ error: 'Company name and claim are required' }, { status: 400 });
    }

    // Simulate backend processing time
    await new Promise(resolve => setTimeout(resolve, 5000));

    // Mock Response based on expected format
    return NextResponse.json({
      company_name,
      claim,
      industry,
      status: "success",
      esg_score: 42,
      risk_level: "High",
      confidence: 0.85,
      pillar_scores: {
        environmental: 42,
        social: 78,
        governance: 85
      },
      evidence: [
        {
          id: 1,
          title: "Scope 3 emissions omit supply chain logistics",
          source: "EU ESG Directive Compliance Scan",
          date: "2023-10-15",
          link: "#",
          type: "regulatory"
        },
        {
          id: 2,
          title: "Investigation into battery sourcing practices",
          source: "Financial Times",
          date: "2023-11-20",
          link: "#",
          type: "news"
        },
        {
          id: 3,
          title: "Q3 Sustainability Report Discrepancies",
          source: "Internal AI Audit",
          date: "2024-01-05",
          link: "#",
          type: "financial"
        }
      ],
      agent_outputs: [
        { name: "Claim Extraction", status: "completed" },
        { name: "Evidence Retrieval", status: "completed" },
        { name: "Contradiction Analysis", status: "completed", alert: true },
        { name: "Industry Comparison", status: "completed" },
        { name: "Risk Scoring", status: "completed" },
        { name: "Report Generation", status: "completed" }
      ],
      shap_explanation: [
        { factor: "Carbon intensity", effect: "increases", weight: 0.45 },
        { factor: "Missing Scope 3 data", effect: "increases", weight: 0.35 },
        { factor: "Board diversity", effect: "decreases", weight: 0.15 },
        { factor: "Supply chain audits", effect: "increases", weight: 0.20 }
      ],
      summary: "High risk of greenwashing detected. The claim heavily contradicts external regulatory findings and omits significant Scope 3 emission data."
    }, { status: 200 });

  } catch (error) {
    console.error('Analysis error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
