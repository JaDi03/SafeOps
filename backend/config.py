"""
SafeOps — Configuration
Centralized config loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_ROBOTICS_MODEL: str = "gemini-robotics-er-1.6-preview"
    GEMINI_PRO_MODEL: str = "gemini-2.5-pro-preview-06-05"
    GEMINI_FLASH_MODEL: str = "gemini-2.0-flash"

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Safety thresholds
    RISK_THRESHOLD_HIGH: int = int(os.getenv("RISK_THRESHOLD_HIGH", "75"))
    RISK_THRESHOLD_MEDIUM: int = int(os.getenv("RISK_THRESHOLD_MEDIUM", "40"))
    ANALYSIS_INTERVAL_MS: int = int(os.getenv("ANALYSIS_INTERVAL_MS", "3000"))

    # OSHA reference costs (USD) — used for financial impact calculations
    OSHA_FINE_SERIOUS: int = 15_625
    OSHA_FINE_WILLFUL: int = 156_259
    AVG_INJURY_COST: int = 42_000
    AVG_FATALITY_COST: int = 1_220_000
    AVG_DOWNTIME_COST_PER_HOUR: int = 8_500


settings = Settings()
