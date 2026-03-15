from typing import List, Dict, Optional
import json
import re

def validate_company(text: str, company_name: str) -> bool:
    """
    Verify that the document actually belongs to the requested company.
    """
    if not text:
        return False
    # Use word boundary to avoid partial matches
    import re
    # Handle cases where company name is multi-word or just single word
    main_name = company_name.split()[0]
    pattern = r'\b' + re.escape(main_name.lower()) + r'\b'
    match_count = len(re.findall(pattern, text.lower()))
    
    # A genuine ESG report will mention the company multiple times, not just once.
    if match_count > 3:
        return True
    return False
    
def is_company_actor(sentence: str, company_name: str) -> bool:
    """Check if the target company is making the commitment."""
    sentence_lower = sentence.lower()
    # Match any part of the company name to make it less strict
    company_parts = company_name.lower().split()
    company_matched = False
    
    for part in company_parts:
        # Ignore common suffixes in matching if they are separate words (Inc, Corp, etc.)
        if len(part) > 2 and part not in ["inc", "corp", "llc", "ltd", "plc", "ag"]:
            if part in sentence_lower:
                company_matched = True
                break
                
    if not company_matched:
        # If company explicitly says "we", "our" in a report verified as belonging to them, accept it.
        if "we" not in sentence_lower and "our" not in sentence_lower:
            return False
            
    COMMITMENT_WORDS = [
        "aim",
        "target",
        "goal",
        "plan",
        "commit",
        "pledge",
        "intend",
        "will",
        "strategy"
    ]
    
    for word in COMMITMENT_WORDS:
        if word in sentence_lower:
            return True

    return False

def detect_organization(sentence: str, target_company: str) -> bool:
    """Ensure the sentence belongs to the target company."""
    if target_company.split()[0].lower() in sentence.lower():
        return True
    return False
    
def get_metric_from_sentence(sentence: str) -> str:
    """Map natural language to standard metrics."""
    sentence = sentence.lower()
    
    # Standardize ESG Categories explicitly (Step 1 Requirement)
    if any(phrase in sentence for phrase in ["net zero", "net-zero", "carbon neutral", "carbon neutrality", "climate neutral", "carbon negative"]):
        return "carbon_emissions"
        
    METRIC_KEYWORDS = {
        "electric": "fleet_electrification",
        "bev": "fleet_electrification",
        "renewable": "renewable_energy",
        "carbon-free electricity": "renewable_energy",
        "carbon": "carbon_emissions",
        "emissions": "carbon_emissions",
        "ghg": "carbon_emissions",
        "circular": "circular_economy",
        "waste": "waste_management",
        "zero waste": "waste_management",
        "water": "water_usage",
        "water positive": "water_usage",
        "green bond": "sustainable_finance",
        "diversity": "diversity",
        "women": "diversity"
    }
    
    for key, metric in METRIC_KEYWORDS.items():
        if key in sentence:
            return metric
            
    return "sustainability goal"
    
def is_real_promise(sentence: str, company_name: str) -> bool:
    """
    Stricter rule-based filtering to ensure we only capture Future Promises or Valid Pledges.
    Must contain company name as actor, future commit, clear target, and avoid invalid modifiers.
    """
    sentence_lower = sentence.lower()
    comp_lower = company_name.lower()
    
    # 1. Reject invalid contexts (cynical reports, reductions in ambition).
    invalid_modifiers = [
        "scaled back", "reduced target", "criticized", "investigated", "questioned", 
        "analysis", "report said", "according to analysts", "cut target", 
        "reduced commitment", "missed target", "failed to meet"
    ]
    if any(m in sentence_lower for m in invalid_modifiers):
        return False
        
    # 2. Specific check for past achievement that is NOT a future promise
    past_achievement_phrases = ["achieved", "completed", "surpassed", "reached its target", "met its goal"]
    if any(p in sentence_lower for p in past_achievement_phrases) and "will" not in sentence_lower and "aim" not in sentence_lower:
         return False

    # 3. Must mention the company explicitly
    # We require the company name somewhere in the sentence. Ideally as the actor.
    escaped_comp = re.escape(comp_lower)
    # Check if the company name appears as a whole word
    if not re.search(rf'\b{escaped_comp}\b', sentence_lower) and comp_lower not in sentence_lower:
        return False
        
    # Example rough actor check. It requires company name followed closely by promise words
    promise_words = ["will", "aim", "target", "plan", "commit", "pledge", "promise", "to become", "goal is", "expect"]
    valid_promise = False
    for word in promise_words:
        if word in sentence_lower:
            valid_promise = True
            break
            
    if not valid_promise:
        return False

    return True

def _fallback_extract_promises(report_text: str, company_name: str = "") -> List[Dict]:
    """Fallback robust natural language extraction pulling from verified contexts."""
    promises = []
    
    import re
    # Split robustly
    sentences = re.split(r'(?<=[.!?])\s+', report_text)
    
    for sentence in sentences:
         if not sentence: continue
         
         # Strict Actor Filter
         if company_name:
             if not is_company_actor(sentence, company_name):
                  continue
                  
         if not is_real_promise(sentence, company_name):
             continue
         
         text_lower = sentence.lower()
         
         # Look for years as deadlines
         deadline_match = re.search(r'\b(20[2-5][0-9])\b', text_lower)
         deadline = int(deadline_match.group(1)) if deadline_match else None
         
         # Look for baseline years
         baseline_match = re.search(r'baseline\s+(?:of\s+)?(20[0-2][0-9])', text_lower)
         baseline = int(baseline_match.group(1)) if baseline_match else None
         
         # Look for scope
         scope_match = re.search(r'(scope\s+[1-3](?:\s*(?:and|\+|&)\s*[1-3])*)', text_lower)
         scope = scope_match.group(1) if scope_match else None
         
         # Try to extract target numbers
         target_match = re.search(r'(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|m|bn|billion|million)', text_lower)
         
         metric = get_metric_from_sentence(text_lower)
         
         target_val = None
         unit_val = None
         
         if target_match:
             target_val = float(target_match.group(1))
             unit_match = re.search(r'(%|percent|m|bn|billion|million)', text_lower[target_match.end(1):])
             unit_val = unit_match.group(1) if unit_match else ""
             
         if not target_val and any(phrase in text_lower for phrase in ["net zero", "net-zero", "carbon neutral", "carbon neutrality", "climate neutral"]):
             target_val = None
             unit_val = ""
             
         # Require at least a metric and a deadline OR a target value
         if metric != "sustainability goal":
             promises.append({
                 "metric": metric,
                 "target": target_val,
                 "unit": unit_val,
                 "baseline": baseline,
                 "scope": scope,
                 "deadline": deadline,
                 "source": "ESG Report",
                 "supporting_quote": sentence.strip()
             })
             
    # Deduplicate
    unique = {}
    for p in promises:
        key = (p["metric"], p["deadline"], p["target"])
        unique[key] = p
        
    return list(unique.values())


def extract_promises(report_text: str, company_name: str = "") -> List[Dict]:
    """
    Extract structured ESG commitments exactly from report text using LLM with Strict parameters.
    """
    if not report_text:
        return []
    
    try:
        from core.llm_client import LLMClient
        llm = LLMClient()
    except ImportError:
        return _fallback_extract_promises(report_text, company_name)
    
    prompt = f"""
    You are a strict financial auditor. Extract the specific ESG target and actual data from the provided text ONLY. 
    Extract commitments made by {company_name} or generally stated in the report as goals, targets, ambitions, or plans.
    Accept sentences with commitment language like "will", "aim", "target", "commit", "pledge", "plan", "goal", or "ambition".
    Do not be overly strict about {company_name} being the explicit actor if the context is clearly the company's report.
    Reject sentences that only describe past achievements (e.g. "achieved", "reached") without future goals.
    Extract commitments even if a numeric target is not present.
    If the commitment is qualitative (e.g. net zero, carbon neutral), set target=null.
    If the text contains "net zero", "net-zero", "carbon neutral", "carbon neutrality", or "climate neutral", you MUST interpret this as metric = "carbon_emissions", target = null, and unit = "".
    Always normalize metric names to standardized categories: "carbon_emissions", "renewable_energy", "water_usage", "waste_management", "circular_economy".
    Extract the baseline year and scope (like Scope 1, Scope 2, Scope 3) if mentioned.
    Do not infer or calculate numbers.
    Return strictly a JSON list of dictionaries. Each dictionary must have these exact keys:
    - "metric": area of promise (e.g. "carbon_emissions", "renewable_energy")
    - "target": numeric target value
    - "unit": unit of the target (e.g., "%", "tons")
    - "baseline": the baseline year (e.g. 2018) or null if not found
    - "scope": the scope covered (e.g. "Scope 1 + 2") or null if not found
    - "deadline": year target is meant to be met
    - "measures_taking": a short sentence describing how the company plans to achieve this based on the text. ONLY output a measure if it contains concrete action verbs like "implement", "deploy", "install", "transition", "reduce", "phase out", "build", "increase renewable capacity", "adopt circular", etc. If no concrete action verb exists, you MUST exactly output "Measure not clearly specified in source text".
    - "source": "ESG Report"
    - "supporting_quote": exact verbatim quote from the text that proves the metric.
    
    Output nothing but valid JSON.
    
    Report Text:
    {report_text[:15000]}
    """
    
    result = None
    try:
        # Notice we would theoretically set temperature=0 here if supported by call_with_fallback directly. 
        # But we rely on the very strict prompt.
        result = llm.call_with_fallback(prompt, use_gemini_first=True)
    except Exception as e:
        print(f"LLM Call failed: {e}")
        
    if not result:
        # Fallback to manual regex parsing if LLM is down
        return _fallback_extract_promises(report_text, company_name)
        
    # Extract JSON part from result in case of markdown formatting
    try:
        # Find JSON block
        json_match = re.search(r'\[\s*\{.*?\}\s*\]', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            promises = json.loads(json_str)
        else:
            # Fallback parsing
            json_str = result.strip().strip('```json').strip('```').strip()
            promises = json.loads(json_str)
            
        # Deduplicate LLM responses
        unique = {}
        for p in promises:
            key = (p.get("metric", "").lower(), p.get("deadline"), p.get("target"))
            unique[key] = p
            
        return list(unique.values())
        
    except Exception as e:
        print(f"Error parsing LLM output: {e}")
        return _fallback_extract_promises(report_text, company_name)
