"""
Pytest fixtures for Academy Program test suite.
Provides async test client, database connections, and test data setup.
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator, Dict, Any
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import redis.asyncio as redis
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

# Import the FastAPI app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.db.postgres import Base, get_postgres_session
from app.db.mongodb import get_mongodb
from app.db.redis import get_redis, RedisClient


# Test database URLs (use same DBs for simplicity, but clean between tests)
TEST_POSTGRES_URL = settings.postgres_url
TEST_MONGO_URL = settings.mongo_url
TEST_REDIS_URL = settings.redis_url_resolved


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create async engine for testing."""
    engine = create_async_engine(TEST_POSTGRES_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_factory(test_engine):
    """Create async session factory."""
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
async def mongo_client() -> AsyncGenerator[AsyncIOMotorClient, None]:
    """Create MongoDB client for testing."""
    client = AsyncIOMotorClient(TEST_MONGO_URL)
    yield client
    client.close()


@pytest.fixture
async def mongo_db(mongo_client) -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Get MongoDB database for testing."""
    db = mongo_client[settings.MONGO_DB]
    yield db


@pytest.fixture(scope="session")
async def redis_client_session() -> AsyncGenerator[redis.Redis, None]:
    """Create Redis client for testing."""
    client = redis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    await client.close()


@pytest.fixture
async def redis_test_client(redis_client_session) -> AsyncGenerator[RedisClient, None]:
    """Get Redis client wrapper for testing."""
    rc = RedisClient()
    rc.client = redis_client_session
    yield rc


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ================== Test Data Fixtures ==================

@pytest.fixture
def test_admin_credentials() -> Dict[str, str]:
    """Admin test credentials."""
    return {
        "email": "admin@academy.edu",
        "password": "admin123",
        "name": "Test Admin",
        "role": "admin"
    }


@pytest.fixture
def test_student_credentials() -> Dict[str, str]:
    """Student test credentials."""
    return {
        "email": "student1@academy.edu",
        "password": "student123",
        "name": "John Student",
        "role": "student"
    }


@pytest.fixture
def test_teacher_credentials() -> Dict[str, str]:
    """Teacher test credentials."""
    return {
        "email": "teacher1@academy.edu",
        "password": "teacher123",
        "name": "Jane Teacher",
        "role": "teacher"
    }


@pytest.fixture
def test_store_credentials() -> Dict[str, str]:
    """Store staff test credentials."""
    return {
        "email": "store1@academy.edu",
        "password": "store123",
        "name": "Store Staff",
        "role": "store"
    }


# ================== Token Fixtures ==================

async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    """Helper to get auth token via login."""
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": password}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return ""


@pytest.fixture
async def admin_token(async_client: AsyncClient, test_admin_credentials) -> str:
    """Get admin JWT token."""
    token = await get_auth_token(
        async_client,
        test_admin_credentials["email"],
        test_admin_credentials["password"]
    )
    return token


@pytest.fixture
async def student_token(async_client: AsyncClient, test_student_credentials) -> str:
    """Get student JWT token."""
    token = await get_auth_token(
        async_client,
        test_student_credentials["email"],
        test_student_credentials["password"]
    )
    return token


@pytest.fixture
async def teacher_token(async_client: AsyncClient, test_teacher_credentials) -> str:
    """Get teacher JWT token."""
    token = await get_auth_token(
        async_client,
        test_teacher_credentials["email"],
        test_teacher_credentials["password"]
    )
    return token


@pytest.fixture
async def store_token(async_client: AsyncClient, test_store_credentials) -> str:
    """Get store staff JWT token."""
    token = await get_auth_token(
        async_client,
        test_store_credentials["email"],
        test_store_credentials["password"]
    )
    return token


def auth_header(token: str) -> Dict[str, str]:
    """Create authorization header."""
    return {"Authorization": f"Bearer {token}"}


# ================== Test Data Constants ==================

TEST_PROGRAM_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TEST_CLASS_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TEST_STUDENT_ID = "cf036f84-bc85-48f8-ba5f-7d424fc939a2"
