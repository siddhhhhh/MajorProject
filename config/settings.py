import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

class Settings(BaseModel):
    # API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
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
    
    class Config:
        env_file = ".env"

settings = Settings()
