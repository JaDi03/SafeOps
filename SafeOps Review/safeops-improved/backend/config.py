"""
SafeOps -- Configuration
Centralized config loaded from environment variables.
Includes VEEA Lobster Trap and X402 settings.
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

    # VEEA Lobster Trap -- prompt security layer
    LOBSTER_TRAP_ENABLED: bool = os.getenv("LOBSTER_TRAP_ENABLED", "false").lower() == "true"
    LOBSTER_TRAP_URL: str = os.getenv("LOBSTER_TRAP_URL", "http://localhost:8080")

    # X402 -- optional machine-to-machine payments
    X402_ENABLED: bool = os.getenv("X402_ENABLED", "false").lower() == "true"
    X402_WALLET_ADDRESS: str = os.getenv("X402_WALLET_ADDRESS", "")
    X402_NETWORK: str = os.getenv("X402_NETWORK", "base")  # base, solana, polygon

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Safety thresholds
    RISK_THRESHOLD_HIGH: int = int(os.getenv("RISK_THRESHOLD_HIGH", "75"))
    RISK_THRESHOLD_MEDIUM: int = int(os.getenv("RISK_THRESHOLD_MEDIUM", "40"))
    ANALYSIS_INTERVAL_MS: int = int(os.getenv("ANALYSIS_INTERVAL_MS", "3000"))

    # OSHA reference costs (USD) -- used for financial impact calculations
    OSHA_FINE_SERIOUS: int = 15_625
    OSHA_FINE_WILLFUL: int = 156_259
    AVG_INJURY_COST: int = 42_000
    AVG_FATALITY_COST: int = 1_220_000
    AVG_DOWNTIME_COST_PER_HOUR: int = 8_500

    # Multi-view analysis
    MULTIVIEW_FUSION_ENABLED: bool = True  # Enable fused 4-camera spatial analysis
    AGENTIC_VISION_ENABLED: bool = True    # Enable code execution for instrument reading

    # Digital Twin
    DIGITAL_TWIN_ENABLED: bool = True

    # Memory / persistence
    MAX_MEMORY_EVENTS: int = 100  # Keep last N events in memory


settings = Settings()
