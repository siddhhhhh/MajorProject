# ESG Mismatch & Greenwashing Detector

The **ESG Mismatch Detector** is a robust automated pipeline designed to identify potential "greenwashing" by corporate entities. It achieves this by automatically downloading a company's official sustainability reports, extracting their future and past ESG (Environmental, Social, and Governance) commitments, and rigorously cross-referencing those claims against external, real-world evidence (such as regulatory actions, news, and environmental databases).

## 🚀 How It Works

The pipeline follows a strict multi-step process to ensure high-fidelity data extraction and mismatch detection:

1. **Company Resolution (`company_resolver.py`)**  
   Normalizes the requested company name and identifies its core domain.
   
2. **Report Collection (`report_collector.py`)**  
   Intelligently crawls the web (using DuckDuckGo) to discover the company's official `/sustainability` or ESG pages. It scrapes for PDF links, ranks them based on relevance (e.g., keywords like "2024", "ESG", "Sustainability"), downloads the top candidate, and validates that it belongs to the target company.
   
3. **Promise Extraction (`promise_extractor.py`)**  
   Utilizes an LLM (Gemini with Groq fallback) via a highly strict financial auditor prompt to extract actual corporate commitments. 
   - Normalizes metric namespaces (e.g., mapping "green bonds" to "sustainable_finance").
   - Extracts exact baselines, targets, units, deadlines, and scopes.
   - Enforces **Action-Verb Validation** to ensure the "Measures Being Taken" field only captures concrete operational actions (e.g., "deploy", "install", "transition") rather than vague corporate fluff.

4. **External Evidence Collection (`evidence_collector.py`)**  
   Queries external, trusted sources (like EPA, SEC, trusted news sites, and regulatory bodies) to find verified performance metrics or qualitative reporting that contradicts the company's claims.
   
5. **Comparison & Gap Engine (`comparison_engine.py`)**  
   A deterministic rules-based engine that compares extracted promises against external evidence.
   - **Quantitative Matching:** Analyzes if actual emissions or metrics failed to meet the targeted goals and calculates the gap.
   - **Qualitative Violation Detection:** Directly flags severe regulatory violations (like the Volkswagen emissions scandal or FTC fraud notices) even if they lack matching mathematical data.
   - **Deduplication:** Groups multiple promises affected by the same external violation to avoid artificially inflating the mismatch count.

6. **Pipeline Orchestration (`pipeline.py`)**  
   Ties all modules together, manages a 24-hour cache layer to minimize redundant API calls, and formats the output into a highly readable JSON structure consisting of `Future Commitments` and `Past Promise-Implementation Gaps`.

## 🛠️ Key Features

* **LLM Fallback Mechanism**: Gracefully falls back from Gemini to Groq if rate limits are hit.
* **Qualitative Scandal Sweeping**: Not all greenwashing is purely mathematical. The tool identifies legal and regulatory misconduct text from authoritative sources.
* **Strict Deduplication**: A single regulatory violation triggered by multiple promises will only create *one* discrete mismatch record.
* **Concrete Implementations Only**: Strips out generic marketing speak and demands actual operational action verbs for implementation measures.
* **24-Hour Caching**: Results are stored locally in `cache/esg_analysis/{company_name}.json` to speed up subsequent queries.

## 💻 Usage

To run the pipeline against a target company, use the following interactive command from the project root:

```bash
python -m features.esg_mismatch_detector.pipeline "Microsoft"
```

To run a fresh analysis bypassing the cache, you can delete the previously cached JSON:
```bash
rm -f cache/esg_analysis/volkswagen.json && python -m features.esg_mismatch_detector.pipeline "Volkswagen"
```

## 📄 Example Output

The output is formatted natively to dual-pane JSON that clearly divides the company's stance into unverified or monitored future goals vs. actively failing past pledges.

```json
{
  "Company Analyzed": "Volkswagen",
  "Overall Greenwashing Risk": "High",
  "Executive Summary": "Analysis completed. Detected 1 contradictions or risk flags.",
  "1. Future Commitments & Progress": [
    {
      "Pledge": "Commitment to reach 40 % of Circular Economy by 2040",
      "Status Trend": "Under Verification",
      "Progress/Trend": "Evaluating credible sources",
      "Measures Being Taken": "Implementing circular economy strategies such as RE-USE, RE-FURBISH, RE-MANUFACTURE, RE-CYCLE",
      "Source of Measure": "Official ESG Report"
    }
  ],
  "2. Past Promise-Implementation Gaps (Mismatches)": [
    {
      "Failed Pledge": "Carbon Emissions",
      "Expected Target": "Categorical Goal",
      "Actual Verified Performance": "NON-COMPLIANT: Qualitative Failure",
      "Risk Level": "Severe",
      "Evidence Source": "https://www.epa.gov/vw/learn-about-volkswagen-violations",
      "Verified Quote": "Learn about EPA's issued notice of violation (NOV) of the Clean Air Act (CAA) to Volkswagen. The NOV alleges software that circumvent..."
    }
  ]
}
```

## 🏗️ File Structure

* `pipeline.py` - Core entry point, orchestrator, caching logic, and JSON formatter.
* `company_resolver.py` - Standardizes search inputs.
* `report_collector.py` - Web scraping and PDF processing.
* `promise_extractor.py` - LLM interaction for ESG metric mapping, baseline/scope extraction, & action-verb filtering.
* `evidence_collector.py` - Trusted external data aggregator.
* `comparison_engine.py` - Evaluates matches, handles quantitative and qualitative gap logic, formats risk scores.
* `README.md` - Technical documentation.
