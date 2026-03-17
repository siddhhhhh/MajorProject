import os
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

load_dotenv()

class Settings(BaseModel):
    model_config = ConfigDict(env_file=".env")

    # API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    NEWSDATA_API_KEY: str = os.getenv("NEWSDATA_API_KEY", "")
    SEC_API_KEY: str = os.getenv("SEC_API_KEY", "")
    
    # Model Configuration - Updated October 2025
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # ✅ Updated from deprecated 3.1
    GROQ_FAST_MODEL: str = "llama-3.1-8b-instant"  # For very fast operations
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_PRO_MODEL: str = "gemini-2.5-pro"
    
    # Chroma Configuration
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "esg_evidence"
    
    # Agent Configuration
    MAX_RETRIES: int = 3
    TIMEOUT: int = 300
    
    # Weights for risk scoring
    WEIGHTS: dict = {
        "claim_verification": 0.25,
        "evidence_quality": 0.20,
        "source_credibility": 0.20,
        "sentiment_divergence": 0.15,
        "historical_pattern": 0.10,
        "contradiction_severity": 0.10
    }
    
    # =============================================
    # NEW: Regional Configuration (India-focused)
    # =============================================
    DEFAULT_JURISDICTION: str = os.getenv("DEFAULT_JURISDICTION", "India")
    
    # Indian regulatory settings
    SEBI_BRSR_ENABLED: bool = True
    MCA_COMPLIANCE_ENABLED: bool = True
    CPCB_MONITORING_ENABLED: bool = True
    
    # Indian news sources
    INDIAN_NEWS_SOURCES: list = [
        "economic_times",
        "business_standard", 
        "livemint",
        "moneycontrol",
        "hindu_business"
    ]
    
    # Indian grid emission factor (tCO2/MWh) - CEA 2025
    INDIA_GRID_EMISSION_FACTOR: float = 0.71
    
    # =============================================
    # NEW: ClimateBERT Configuration
    # =============================================
    CLIMATEBERT_ENABLED: bool = os.getenv("CLIMATEBERT_ENABLED", "true").lower() == "true"
    CLIMATEBERT_USE_GPU: bool = os.getenv("CLIMATEBERT_USE_GPU", "false").lower() == "true"
    
    # =============================================
    # NEW: Explainability Configuration
    # =============================================
    SHAP_ENABLED: bool = os.getenv("SHAP_ENABLED", "true").lower() == "true"
    LIME_ENABLED: bool = os.getenv("LIME_ENABLED", "true").lower() == "true"
    EXPLAINABILITY_TOP_FEATURES: int = 5
    
    # =============================================
    # NEW: Carbon Accounting Configuration
    # =============================================
    CARBON_SCOPES_ENABLED: list = ["scope1", "scope2", "scope3"]
    GHG_PROTOCOL_VERSION: str = "2024"
    CDP_INTEGRATION_ENABLED: bool = True
    SBTI_VALIDATION_ENABLED: bool = True
    
    # =============================================
    # NEW: Regulatory Scanner Configuration
    # =============================================
    REGULATORY_FRAMEWORKS: list = [
        # Indian
        "SEBI_BRSR",
        "MCA_COMPANIES_ACT",
        "CPCB_EPA",
        "RBI_GREEN_FINANCE",
        "INDIA_BEE_PAT",
        # Global
        "GHG_PROTOCOL",
        "SBTI",
        "GRI_STANDARDS",
        "CDP",
        # International
        "EU_CSRD",
        "EU_TAXONOMY",
        "SEC_CLIMATE",
        "UK_FCA_ANTIGREENWASHING"
    ]
    
settings = Settings()
GREENWASHING_THRESHOLD = 50.0  # auto-computed
