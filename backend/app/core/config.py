from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "LegalTech SaaS Enterprise"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "enterprise_super_secret_key_legaltech_2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/legaltech_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
