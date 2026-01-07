from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # App settings
    app_name: str = "Void Tax System"
    debug: bool = True
    
    # Scanning settings
    scan_interval_ms: int = 1000  # Frontend frame send interval (1 second for better performance)
    cache_cooldown_min: int = 5  # Minutes before re-checking same plate
    ocr_confidence_min: float = 0.5  # Minimum OCR confidence threshold (lowered for demo)
    
    # External API settings
    external_api_url: str = "http://localhost:8001/api"
    external_api_timeout: int = 10
    
    # Database settings
    database_url: str = "sqlite+aiosqlite:///./void_tax.db"
    
    # Fine settings
    road_tax_fine_amount: float = 150.00
    insurance_fine_amount: float = 300.00
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

