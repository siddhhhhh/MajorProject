"""
ESG Agents Package
Multi-agent system for greenwashing detection and ESG analysis

Core Agents:
- ClaimExtractor: Extract structured ESG claims
- EvidenceRetriever: Gather multi-source evidence
- ContradictionAnalyzer: Detect claim-evidence contradictions
- CredibilityAnalyst: Assess source reliability
- SentimentAnalyzer: Linguistic and sentiment analysis
- HistoricalAnalyst: Historical ESG pattern analysis
- RiskScorer: Final greenwashing risk scoring
- FinancialAnalyst: Financial-ESG correlation
- IndustryComparator: Peer comparison
- ConflictResolver: Multi-agent debate resolution
- ConfidenceScorer: Confidence calibration
- RealtimeMonitor: Real-time ESG monitoring

New Agents (2026):
- CarbonExtractor: Scope 1, 2, 3 emissions extraction
- GreenwishingDetector: Greenwishing/Greenhushing detection
- RegulatoryScanner: Regulatory compliance verification
- SocialAgent: Social pillar forensic analysis
- GovernanceAgent: Governance pillar forensic analysis
"""

import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from .claim_extractor import ClaimExtractor
from .evidence_retriever import EvidenceRetriever
from .contradiction_analyzer import ContradictionAnalyzer
from .credibility_analyst import CredibilityAnalyst
from .sentiment_analyzer import SentimentAnalyzer
from .historical_analyst import HistoricalAnalyst
from .risk_scorer import RiskScorer
from .financial_analyst import FinancialAnalyst
# IndustryComparator is deprecated.
from .conflict_resolver import ConflictResolver
from .confidence_scorer import ConfidenceScorer
try:
    from .realtime_monitor import RealTimeMonitor
except Exception:
    RealTimeMonitor = None

# New 2026 Agents
from .carbon_extractor import CarbonExtractor, get_carbon_extractor
from .greenwishing_detector import GreenwishingDetector, get_greenwishing_detector
from .regulatory_scanner import RegulatoryHorizonScanner, get_regulatory_scanner
from .social_agent import SocialAgent
from .governance_agent import GovernanceAgent

__all__ = [
    # Core Agents
    'ClaimExtractor',
    'EvidenceRetriever',
    'ContradictionAnalyzer',
    'CredibilityAnalyst',
    'SentimentAnalyzer',
    'HistoricalAnalyst',
    'RiskScorer',
    'FinancialAnalyst',

    'ConflictResolver',
    'ConfidenceScorer',
    'RealTimeMonitor',
    
    # New 2026 Agents
    'CarbonExtractor',
    'get_carbon_extractor',
    'GreenwishingDetector',
    'get_greenwishing_detector',
    'RegulatoryHorizonScanner',
    'get_regulatory_scanner',
    'SocialAgent',
    'GovernanceAgent'
]
