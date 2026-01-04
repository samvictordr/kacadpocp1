"""
Application configuration.
All settings are loaded from environment variables with sensible defaults for local development.

Render Compatibility:
- Supports direct DATABASE_URL, REDIS_URL, MONGODB_URI environment variables
- Falls back to component-based URLs for local development
- Automatically configures SSL for production database connections
"""
from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Academy Program"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False  # Default to False for production safety
    SECRET_KEY: str = secrets.token_urlsafe(32)
    
    # JWT Settings
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # PostgreSQL - Direct URL takes precedence (Render provides this)
    DATABASE_URL: Optional[str] = None  # e.g., postgresql://user:pass@host:5432/db
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "academy"
    POSTGRES_PASSWORD: str = "academy_secret"
    POSTGRES_DB: str = "academy_db"
    
    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL. Prefers DATABASE_URL if set."""
        if self.DATABASE_URL:
            # Render provides postgresql:// but asyncpg needs postgresql+asyncpg://
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "+asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            # Ensure SSL is enabled for production (Render requires SSL)
            # asyncpg uses 'ssl=require' not 'sslmode=require'
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if "ssl" not in query_params and "sslmode" not in query_params and not self.DEBUG:
                query_params["ssl"] = ["require"]
                new_query = urlencode(query_params, doseq=True)
                url = urlunparse(parsed._replace(query=new_query))
            
            return url
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # MongoDB - Direct URL takes precedence (MongoDB Atlas provides this)
    MONGODB_URI: Optional[str] = None  # e.g., mongodb+srv://user:pass@cluster.mongodb.net/db
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_USER: Optional[str] = "academy"
    MONGO_PASSWORD: Optional[str] = "academy123"
    MONGO_DB: str = "academy_identity"
    
    @property
    def mongo_url(self) -> str:
        """Get MongoDB connection URL. Prefers MONGODB_URI if set."""
        if self.MONGODB_URI:
            return self.MONGODB_URI
        if self.MONGO_USER and self.MONGO_PASSWORD:
            return f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}/?authSource=admin"
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"
    
    # Redis - Direct URL takes precedence (Render provides this)
    REDIS_URL: Optional[str] = None  # e.g., redis://user:pass@host:6379
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    @property
    def redis_url_resolved(self) -> str:
        """Get Redis connection URL. Prefers REDIS_URL if set."""
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def redis_ssl_enabled(self) -> bool:
        """Check if Redis connection should use SSL (Render uses rediss:// for TLS)."""
        if self.REDIS_URL:
            return self.REDIS_URL.startswith("rediss://")
        return False
    
    # Token TTLs (in seconds)
    ATTENDANCE_QR_TTL: int = 86400  # 24 hours
    STORE_TOKEN_TTL: int = 86400    # 24 hours
    
    # Allowance defaults
    DEFAULT_DAILY_ALLOWANCE: float = 100.0
    
    # CORS - Configurable for production
    CORS_ORIGINS: str = "*"  # Comma-separated list or "*" for all
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
