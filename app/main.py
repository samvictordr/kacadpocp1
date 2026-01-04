"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import sys

from app.core.config import settings
from app.db.postgres import init_postgres, close_postgres
from app.db.mongodb import init_mongodb, close_mongodb
from app.db.redis import init_redis, close_redis

# Import routers
from app.api.auth import router as auth_router
from app.api.student import router as student_router
from app.api.teacher import router as teacher_router
from app.api.store import router as store_router
from app.api.admin import router as admin_router


def _mask_url(url: str) -> str:
    """Mask password in database URLs for logging."""
    if '@' in url:
        # Split at @ to separate credentials from host
        parts = url.split('@')
        creds = parts[0]
        host = '@'.join(parts[1:])
        # Mask the password
        if ':' in creds:
            scheme_user = creds.rsplit(':', 1)[0]
            return f"{scheme_user}:****@{host}"
    return url


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initializes and closes database connections.
    Fails fast if any database connection fails.
    """
    # Startup
    print("=" * 50)
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Debug mode: {settings.DEBUG}")
    print("=" * 50)
    
    # Log database connection sources
    print("\nDatabase Configuration:")
    print(f"  PostgreSQL: {'Render (DATABASE_URL)' if settings.DATABASE_URL else 'Local (component config)'}")
    print(f"  MongoDB: {'Atlas (MONGODB_URI)' if settings.MONGODB_URI else 'Local (component config)'}")
    print(f"  Redis: {'Render (REDIS_URL)' if settings.REDIS_URL else 'Local (component config)'}")
    if settings.redis_ssl_enabled:
        print("  Redis TLS: Enabled")
    print()
    
    try:
        print("Connecting to PostgreSQL...")
        await init_postgres()
        print("✓ PostgreSQL connected")
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        sys.exit(1)
    
    try:
        print("Connecting to MongoDB...")
        await init_mongodb()
        print("✓ MongoDB connected")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        await close_postgres()
        sys.exit(1)
    
    try:
        print("Connecting to Redis...")
        await init_redis()
        print("✓ Redis connected")
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        await close_postgres()
        await close_mongodb()
        sys.exit(1)
    
    print("=" * 50)
    print("All services connected. Server ready.")
    print("=" * 50)
    
    yield
    
    # Shutdown
    print("Shutting down...")
    await close_postgres()
    await close_mongodb()
    await close_redis()
    print("All connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="University Attendance and Allowance System - Phase 1",
    lifespan=lifespan
)

# Configure CORS for PWA access
# Parse CORS_ORIGINS: can be "*" or comma-separated list
cors_origins = settings.CORS_ORIGINS
if cors_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(teacher_router)
app.include_router(store_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """
    Detailed health check that verifies database connections.
    Used by Render and other platforms for liveness checks.
    """
    from app.db.postgres import engine
    from app.db.mongodb import mongodb
    from app.db.redis import redis_client
    
    health = {
        "status": "healthy",
        "databases": {}
    }
    
    # Check PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["databases"]["postgres"] = "connected"
    except Exception as e:
        health["databases"]["postgres"] = f"error: {str(e)}"
        health["status"] = "unhealthy"
    
    # Check MongoDB
    try:
        await mongodb.db.command("ping")
        health["databases"]["mongodb"] = "connected"
    except Exception as e:
        health["databases"]["mongodb"] = f"error: {str(e)}"
        health["status"] = "unhealthy"
    
    # Check Redis
    try:
        await redis_client.client.ping()
        health["databases"]["redis"] = "connected"
    except Exception as e:
        health["databases"]["redis"] = f"error: {str(e)}"
        health["status"] = "unhealthy"
    
    return health
