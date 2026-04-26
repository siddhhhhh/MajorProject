from typing import Dict, List
import re

_SUFFIX_PATTERN = re.compile(
    r"\b(inc\.?|corp\.?|corporation|co\.?|company|llc|ltd\.?|limited|plc|group|holdings?)\b",
    flags=re.IGNORECASE,
)

ENERGY_MAJOR_NAMES = {
    "bp",
    "shell",
    "exxon",
    "chevron",
    "totalenergies",
    "saudi aramco",
    "aramco",
    "eni",
    "equinor",
}


def normalize_company_name(company_name: str) -> str:
    """Normalize company input into a clean canonical name."""
    name = re.sub(r"\s+", " ", (company_name or "").strip())
    if not name:
        return ""

    # Insert spaces into CamelCase inputs like JPMorganChase -> JP Morgan Chase.
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    # Normalize punctuation around legal suffixes.
    name = re.sub(r"[,&()]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def generate_company_aliases(company_name: str) -> List[str]:
    """Generate robust aliases for retrieval and mention matching."""
    canonical = normalize_company_name(company_name)
    if not canonical:
        return []

    aliases = {
        canonical,
        canonical.replace(" ", ""),
        canonical.replace("&", "and"),
    }

    no_suffix = _SUFFIX_PATTERN.sub("", canonical)
    no_suffix = re.sub(r"\s+", " ", no_suffix).strip()
    if no_suffix:
        aliases.add(no_suffix)
        aliases.add(no_suffix.replace(" ", ""))

    tokens = [t for t in re.split(r"\s+", canonical) if t]
    if tokens:
        aliases.add(tokens[0])
    if len(tokens) >= 2:
        aliases.add(" ".join(tokens[:2]))

    # Normalize casing for downstream matching, keep title-cased display forms too.
    normalized_aliases = []
    seen = set()
    for alias in aliases:
        clean = re.sub(r"\s+", " ", alias).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized_aliases.append(clean)

    return normalized_aliases


def detect_company_industry(company_name: str, aliases: List[str]) -> str:
    """Classify company into a coarse industry bucket for retrieval strategy."""
    joined = " ".join([company_name] + aliases).lower()
    if any(marker in joined for marker in ENERGY_MAJOR_NAMES):
        return "energy"
    if any(marker in joined for marker in ["oil", "gas", "petroleum", "energy"]):
        return "energy"
    return "general"


def resolve_company(company_name: str) -> Dict[str, object]:
    """
    Normalize company name and prepare search queries.
    """
    canonical = normalize_company_name(company_name)
    aliases = generate_company_aliases(canonical)
    industry = detect_company_industry(canonical, aliases)
    high_signal_company = industry == "energy"

    search_terms = [
        f"{canonical} ESG report",
        f"{canonical} sustainability report",
        f"{canonical} environmental report",
        f"{canonical} investor relations",
    ]

    # Add alias-based queries for harder entity forms.
    for alias in aliases[:4]:
        if alias.lower() == canonical.lower():
            continue
        search_terms.append(f"{alias} ESG report")

    return {
        "company": canonical,
        "aliases": aliases,
        "search_terms": search_terms,
        "industry": industry,
        "high_signal_company": high_signal_company,
    }
