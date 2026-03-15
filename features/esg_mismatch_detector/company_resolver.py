from typing import Dict, List

def resolve_company(company_name: str) -> Dict[str, List[str]]:
    """
    Normalize company name and prepare search queries.
    Args:
        company_name (str): Raw company name input.
    Returns:
        Dict[str, List[str]]: Normalized company info and search terms.
    """
    normalized = company_name.strip()
    search_terms = [
        f"{normalized} ESG report",
        f"{normalized} sustainability report",
        f"{normalized} environmental report",
        f"{normalized} investor relations"
    ]
    return {"company": normalized, "search_terms": search_terms}
