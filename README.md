# 🌱 ESGLens: Advanced AI-Powered ESG Intelligence & Greenwashing Detection System

ESGLens is a state-of-the-art, enterprise-grade platform engineered to definitively assess corporate Environmental, Social, and Governance (ESG) claims. Moving far beyond keyword matching or simple LLM prompts, ESGLens utilizes a complex **LangGraph-driven multi-agent architecture** encompassing over 20 highly specialized AI agents, deterministic scoring algorithms, multi-jurisdiction regulatory databases, and machine learning models.

---

## 🏛️ 1. Core System Architecture & Intelligence Engine

The platform is built on a modular, asynchronous backbone designed for maximum auditability and precision.

### A. The LangGraph Orchestrator (`core/workflow_phase2.py`)
At the core of ESGLens is a Directed Acyclic Graph (DAG) state machine. Unlike linear pipelines, LangGraph allows for conditional routing, cycles (for debate), and persistent state management.
- **Dynamic Routing (`assess_complexity_node`)**: Every claim is first analyzed for its "linguistic weight." If a claim is simple (e.g., "We like trees"), it follows the Fast Track. If it involves multi-year carbon targets or supply chain claims, it is routed to the **Deep Analysis Track**.
- **The ESGState Object**: A comprehensive JSON-serializable object that travels through the graph, accumulating raw evidence, agent rationales, and intermediate scores. This ensures that every final verdict is "born" from a visible lineage of data.

### B. Persistent Memory & Peer Benchmarking
- **ChromaDB Integration**: The system maintains a vector database of every company ever analyzed. This allows the `peer_comparison_node` to calculate industry-relative percentiles in real-time.
- **Industry Sigmas ($\sigma$)**: We maintain a registry of industry-specific volatility factors. High-impact sectors (like Energy) have higher sigmas to account for the massive scale of their operations, preventing unfair penalization for small reporting errors while highlighting systemic greenwashing.

---

## ⚖️ 2. The Greenwashing Scoring System: Deep Mathematical Justification

The Greenwashing Risk Score (**GW**) is the system's primary output. It is calculated using a deterministic formula designed to identify the "Gap" between corporate promises and physical reality.

### The Master Formula:
$$GW = \alpha \cdot \text{Gap} + \beta \cdot R + \gamma \cdot \text{Deficit} + \delta \cdot T$$

### **Component 1: Claim Intensity ($C$)** (`agents/claim_intensity_scorer.py`)
$C$ measures the "boldness" and "verifiability" of a claim. It is not a measure of guilt, but a measure of the **burden of proof**.
- **Specificity (0-30 pts)**: Presence of numbers, target years (e.g., 2030), and baselines.
- **Verifiability (0-20 pts)**: Reference to external standards (GRI, TCFD, Scope 1/2/3).
- **Ambiguity Penalty (up to -20 pts)**: Detection of "hedging" language (e.g., "aim to," "strive to," "where feasible").
- **Weighted Classification**: Quantitative targets are weighted at 1.0, while vague marketing claims are weighted at 0.15.

### **Component 2: Execution Gap ($\text{Gap}$)**
The Gap represents the mathematical delta between what is promised ($C$) and what is actually happening ($P$).
- **Formula**: $\text{Gap} = \frac{\max(0, C - P)}{\sigma} \cdot 100$
- **Justification**: If a company makes a "Leadership" claim ($C=90$) but has "Average" performance ($P=50$), the Gap is 40. This gap is then normalized by the industry sigma ($\sigma$) to ensure the penalty is fair relative to peer volatility.

### **Component 3: Controversy Risk ($R$)** (`agents/risk_scorer.py`)
$R$ is a **Blended Metric** (0.6 Verified / 0.4 Probabilistic) that captures active wrongdoing.
- **Verified Regulatory Gaps (60% weight)**: Hard data from SEC filings (Board Independence, Pay Ratio, Whistleblower policies), WBA indicators, and government fines. These are "proven" failures.
- **Probabilistic Contradictions (40% weight)**: Signals from the `contradiction_analyzer.py` which pits claims against news reports and NGO findings.
- **Enhanced Governance Blending**: Governance scores now prioritize high-fidelity `coverageadjustedscore` from WBA/SEC pillar factors over stale top-level scores, with a deterministic fallback to 22.4 for low-disclosure entities.
- **Calculation**: $R = 0.6 \cdot R_{reg} + 0.4 \cdot \min(100, \text{Contradictions} \cdot 20)$.

### **Component 4: Disclosure Deficit ($\text{Deficit}$)**
Based on the **Disclosure Score ($D$)**, which measures transparency.
- **Framework Hits**: Detection of GRI, SASB, TCFD, CDP, ISSB, and SBTi compliance.
- **Third-Party Assurance**: A 20% bonus if the system detects keywords like "limited assurance" or "independently verified."
- **Deficit Logic**: $\text{Deficit} = 100 - D$. Companies that hide their data are penalized for "Greenhushing."

### **Component 5: Temporal Risk ($T$)** (`agents/temporal_consistency_agent.py`)
$T$ measures consistency over time.
- **Claim Escalation**: Does the company make stronger claims each year while its emissions stay flat?
- **Goalpost Shifting**: Detection of baseline changes that make progress look better than it is.
- **Scoring**: 0-30 is consistent; 80-100 is a "High Greenwashing Signal."

---

## 📈 3. Specialized Feature Deep Dives

### **A. Carbon Pathway & CAGR Capping** (`agents/carbon_pathway_modeller.py`)
The system performs a physics-based audit of carbon targets.
- **CAGR Calculation**: It calculates the required Compound Annual Growth Rate of emission reductions.
- **The 45% IEA NZE Ceiling**: If the required reduction rate exceeds **45% per year**, the system flags it as "Physically Impossible." This 45% figure is the maximum scientifically cited rate from the IEA Net Zero 2050 scenario for the most aggressive sectors.
- **Budget Tracking**: Estimates the remaining carbon budget based on current emissions. If the budget is effectively exhausted, the system applies the "IEA NZE Ceiling" to prevent mathematical overflow in the risk score.

### **B. Multi-Agent Debate & Conflict Resolution** (`agents/conflict_resolver.py`)
In the Deep Analysis track, agents often disagree. The **Conflict Resolver** resolves these using an ensemble-voting mechanism:
- **Credibility Scoring**: 
    - Government/Regulatory: **0.95**
    - NGO/Academic: **0.90**
    - Tier-1 Financial Media: **0.85**
    - Company-Controlled Docs: **0.30** (Highly skeptical)
- **Resolution Logic**: If contradicting evidence exists, the system weights each source by its credibility and recency. An LLM-based "Debate Orchestrator" then provides a reasoned verdict on which source is more reliable.

### **C. Regulatory Ingestion & SEC Parsing** (`agents/regulatory_scanner.py`)
The system directly ingests data from the "Truth Sources" of corporate reporting:
- **SEC DEF 14A**: Extracts board independence percentages, CEO-to-median-worker pay ratios, and whistleblower/ethics hotline existence.
- **SEC Form SD**: Scans for "Conflict Minerals" disclosures and supply chain human rights issues.
- **WBA (World Benchmarking Alliance)**: Ingests specific indicator scores and coverage-adjusted metrics for Social and Governance pillars.
- **External Safeguards**: Implements a three-tier fallback logic (Pillar-Specific -> WBA Baseline -> Absolute Fallback) to ensure score integrity in sparse data environments.

---

## 📚 4. Exhaustive Data Source Catalog

ESGLens operates on an multi-layered evidence pool:

1.  **Regulatory Truth Sources**:
    - **SEC EDGAR (US)**: DEF 14A, Form SD, 10-K, 10-Q.
    - **Companies House (UK)**: Strategic reports and gender pay gap filings.
    - **EU Transparency Register**: For lobbying and influence data.

2.  **Global ESG Frameworks**:
    - **WBA (World Benchmarking Alliance)**: Cross-industry performance benchmarks.
    - **CDP (Carbon Disclosure Project)**: The gold standard for climate and water disclosure.
    - **UNFCCC Race to Zero**: Official pledge verification.

3.  **Environmental Intelligence**:
    - **WRI Aqueduct 4.0**: Localized water stress data for corporate facilities.
    - **ClimateBERT**: Specialized LLM for detecting "Climate-Washing" rhetoric.
    - **IPCC Carbon Budgets**: Science-based ceilings for sector-specific emissions.

4.  **Social & Governance Benchmarks**:
    - **ILO (International Labour Organization)**: Global labor violation tracking.
    - **Open Apparel Registry**: Supply chain mapping for the fashion industry.
    - **Glassdoor & Sentiment APIs**: Employee-level sentiment on ESG culture.

5.  **Adversarial News & NGO Data**:
    - **Bing & Google News**: Real-time controversy monitoring.
    - **Greenpeace & InfluenceMap**: Tracking anti-climate lobbying and environmental violations.

---

## 🛠️ 5. Technical Implementation Map (Python Architecture)

| Feature | Primary Python File | Role |
| :--- | :--- | :--- |
| **Pipeline Workflow** | `core/workflow_phase2.py` | Defines the LangGraph nodes and transition logic. |
| **Scoring Engine** | `agents/risk_scorer.py` | The "Brain" that synthesizes all $C, P, R, D, T$ inputs. |
| **Carbon Audit** | `agents/carbon_pathway_modeller.py` | Performs the CAGR math and science-based alignment. |
| **Report Generation** | `core/professional_report_generator.py` | Compiles the 7,000+ line state into a clean executive summary. |
| **Conflict Resolution** | `agents/conflict_resolver.py` | Orchestrates the multi-agent debate and credibility weighting. |
| **Regulatory Scanning** | `agents/regulatory_scanner.py` | The integration layer for SEC, WBA, and external APIs. |
| **Claim Decomposition** | `agents/claim_decomposer.py` | Breaks marketing fluff into atomic, verifiable sub-claims. |
| **Temporal Analysis** | `agents/temporal_consistency_agent.py` | Tracks the "Commitment Ledger" across multiple years. |
| **State Schema** | `core/state_schema.py` | Defines the global `ESGState` structure. |
| **External Enrichment** | `core/agent_wrappers.py` | Orchestrates WBA/SEC data fetching and supplemental evidence injection. |
| **LLM Interface** | `core/llm_call.py` | Standardized wrapper for multi-model LLM calls (GPT-4, Claude, etc.). |

---

## 📄 6. Analysis Outputs & Artifacts

1.  **The Executive Report (`.txt`)**: A professionally formatted, section-by-section breakdown (1. Verdict, 2. Scorecard, 3. Evidence, etc.).
2.  **The Audit JSON (`.json`)**: A full machine-readable trace. Includes the `greenwashing_formula` key which contains the exact $C, P, R, D, T$ values and weights used for that specific run.
3.  **The Fact Graph**: A relational JSON mapping verified facts to their original claim IDs.
