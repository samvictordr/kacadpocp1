"""
Database connection utilities for the dashboard.
"""
import streamlit as st
import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

# Database clients
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis


def get_database_urls():
    """Get database connection URLs from environment."""
    return {
        "postgres": os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/academy"),
        "mongodb": os.getenv("MONGODB_URL", "mongodb://localhost:27017"),
        "mongodb_db": os.getenv("MONGODB_DB", "academy"),
        "redis": os.getenv("REDIS_URL", "redis://localhost:6379")
    }


@st.cache_resource
def get_mongo_client():
    """Get MongoDB client (cached)."""
    urls = get_database_urls()
    return AsyncIOMotorClient(urls["mongodb"])


def get_mongo_db_sync():
    """Get MongoDB database (sync version)."""
    urls = get_database_urls()
    client = get_mongo_client()
    return client[urls["mongodb_db"]]


async def get_mongo_db():
    """Get MongoDB database (async compatible)."""
    urls = get_database_urls()
    client = get_mongo_client()
    return client[urls["mongodb_db"]]


async def get_postgres_pool():
    """Get PostgreSQL connection pool."""
    urls = get_database_urls()
    # Convert postgresql:// to postgres:// if needed for asyncpg
    pg_url = urls["postgres"]
    if pg_url.startswith("postgresql://"):
        pg_url = pg_url.replace("postgresql://", "postgres://", 1)
    
    return await asyncpg.create_pool(pg_url, min_size=1, max_size=5)


async def get_redis_client():
    """Get Redis client."""
    urls = get_database_urls()
    return await aioredis.from_url(urls["redis"])


def init_connections():
    """Initialize database connections."""
    pass  # Connections are created on demand


async def check_postgres_health() -> Dict[str, Any]:
    """Check PostgreSQL health."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            version = await conn.fetchval("SELECT version()")
            
            # Get connection pool stats
            return {
                "status": "healthy",
                "connected": True,
                "version": version.split(",")[0] if version else "Unknown",
                "pool_size": pool.get_size(),
                "pool_free": pool.get_idle_size(),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def check_mongodb_health() -> Dict[str, Any]:
    """Check MongoDB health."""
    try:
        db = get_mongo_db()
        result = await db.command("ping")
        server_info = await db.client.server_info()
        
        return {
            "status": "healthy",
            "connected": True,
            "version": server_info.get("version", "Unknown"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def check_redis_health() -> Dict[str, Any]:
    """Check Redis health."""
    try:
        client = await get_redis_client()
        await client.ping()
        info = await client.info()
        
        return {
            "status": "healthy",
            "connected": True,
            "version": info.get("redis_version", "Unknown"),
            "memory_used": info.get("used_memory_human", "Unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "keys": await client.dbsize(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def get_all_health_status() -> Dict[str, Any]:
    """Get health status of all services."""
    postgres = await check_postgres_health()
    mongodb = await check_mongodb_health()
    redis = await check_redis_health()
    
    all_healthy = all([
        postgres.get("connected"),
        mongodb.get("connected"),
        redis.get("connected")
    ])
    
    return {
        "overall": "healthy" if all_healthy else "degraded",
        "services": {
            "postgres": postgres,
            "mongodb": mongodb,
            "redis": redis
        },
        "timestamp": datetime.now().isoformat()
    }


# ==================== Data Access Functions ====================

async def get_users_from_mongodb(role: Optional[str] = None) -> List[Dict]:
    """Get users from MongoDB."""
    db = get_mongo_db()
    query = {}
    if role:
        query["role"] = role
    
    cursor = db.users.find(query)
    users = await cursor.to_list(length=1000)
    
    # Convert ObjectId to string
    for user in users:
        user["_id"] = str(user["_id"])
    
    return users


async def get_students_from_postgres() -> List[Dict]:
    """Get students from PostgreSQL."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.student_id, s.user_id, s.full_name, s.program_id, s.is_active,
                   p.name as program_name
            FROM students s
            LEFT JOIN programs p ON s.program_id = p.program_id
            ORDER BY s.full_name
        """)
        return [dict(row) for row in rows]


async def get_teachers_from_postgres() -> List[Dict]:
    """Get teachers from PostgreSQL."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.teacher_id, t.user_id, t.full_name, t.program_id, t.is_active,
                   p.name as program_name
            FROM teachers t
            LEFT JOIN programs p ON t.program_id = p.program_id
            ORDER BY t.full_name
        """)
        return [dict(row) for row in rows]


async def get_programs_from_postgres() -> List[Dict]:
    """Get programs from PostgreSQL."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT program_id, name, cost_center, default_daily_allowance, is_active
            FROM programs
            ORDER BY name
        """)
        return [dict(row) for row in rows]


async def get_daily_allowances(date: str = None) -> List[Dict]:
    """Get daily allowances."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT da.allowance_id, da.student_id, da.date, da.base_amount, 
                   da.bonus_amount, da.total_amount, s.full_name
            FROM daily_allowances da
            JOIN students s ON da.student_id = s.student_id
        """
        if date:
            query += f" WHERE da.date = '{date}'"
        query += " ORDER BY da.date DESC, s.full_name LIMIT 100"
        
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]


async def get_transactions(limit: int = 100) -> List[Dict]:
    """Get recent transactions."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT t.transaction_id, t.student_id, t.amount, t.balance_after,
                   t.created_at, t.scanned_by, s.full_name as student_name
            FROM transactions t
            JOIN students s ON t.student_id = s.student_id
            ORDER BY t.created_at DESC
            LIMIT {limit}
        """)
        return [dict(row) for row in rows]


async def get_attendance_records(limit: int = 100) -> List[Dict]:
    """Get recent attendance records."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT a.attendance_id, a.student_id, a.class_id, a.scanned_at,
                   s.full_name as student_name, c.name as class_name
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            JOIN classes c ON a.class_id = c.class_id
            ORDER BY a.scanned_at DESC
            LIMIT {limit}
        """)
        return [dict(row) for row in rows]


# ==================== Telemetry Functions ====================

async def get_telemetry_stats() -> Dict[str, Any]:
    """Get comprehensive telemetry statistics."""
    pool = await get_postgres_pool()
    db = get_mongo_db()
    redis = await get_redis_client()
    
    stats = {}
    
    try:
        async with pool.acquire() as conn:
            # User counts
            stats["total_students"] = await conn.fetchval("SELECT COUNT(*) FROM students WHERE is_active = true")
            stats["total_teachers"] = await conn.fetchval("SELECT COUNT(*) FROM teachers WHERE is_active = true") or 0
            stats["total_programs"] = await conn.fetchval("SELECT COUNT(*) FROM programs WHERE is_active = true")
            
            # Today's stats
            stats["transactions_today"] = await conn.fetchval("""
                SELECT COUNT(*) FROM transactions 
                WHERE DATE(created_at) = CURRENT_DATE
            """) or 0
            
            stats["transaction_amount_today"] = await conn.fetchval("""
                SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE DATE(created_at) = CURRENT_DATE
            """) or 0
            
            stats["attendance_today"] = await conn.fetchval("""
                SELECT COUNT(*) FROM attendance 
                WHERE DATE(scanned_at) = CURRENT_DATE
            """) or 0
            
            # This week stats
            stats["transactions_this_week"] = await conn.fetchval("""
                SELECT COUNT(*) FROM transactions 
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """) or 0
            
            stats["attendance_this_week"] = await conn.fetchval("""
                SELECT COUNT(*) FROM attendance 
                WHERE scanned_at >= CURRENT_DATE - INTERVAL '7 days'
            """) or 0
            
    except Exception as e:
        stats["postgres_error"] = str(e)
    
    try:
        # MongoDB stats
        stats["total_users_mongodb"] = await db.users.count_documents({})
        stats["users_by_role"] = {}
        for role in ["student", "teacher", "store", "admin"]:
            stats["users_by_role"][role] = await db.users.count_documents({"role": role})
    except Exception as e:
        stats["mongodb_error"] = str(e)
    
    try:
        # Redis stats
        info = await redis.info()
        stats["redis_memory"] = info.get("used_memory_human", "Unknown")
        stats["redis_keys"] = await redis.dbsize()
        stats["redis_connected_clients"] = info.get("connected_clients", 0)
    except Exception as e:
        stats["redis_error"] = str(e)
    
    return stats


async def get_transaction_trends(days: int = 7) -> List[Dict]:
    """Get transaction trends for the last N days."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT DATE(created_at) as date, 
                   COUNT(*) as count,
                   COALESCE(SUM(amount), 0) as total_amount,
                   COALESCE(AVG(amount), 0) as avg_amount
            FROM transactions
            WHERE created_at >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        return [dict(row) for row in rows]


async def get_attendance_trends(days: int = 7) -> List[Dict]:
    """Get attendance trends for the last N days."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT DATE(scanned_at) as date, 
                   COUNT(*) as count
            FROM attendance
            WHERE scanned_at >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY DATE(scanned_at)
            ORDER BY date
        """)
        return [dict(row) for row in rows]


async def get_program_breakdown() -> List[Dict]:
    """Get transaction breakdown by program."""
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.name as program_name, p.cost_center,
                   COUNT(t.transaction_id) as transaction_count,
                   COALESCE(SUM(t.amount), 0) as total_amount
            FROM programs p
            LEFT JOIN students s ON p.program_id = s.program_id
            LEFT JOIN transactions t ON s.student_id = t.student_id
            GROUP BY p.program_id, p.name, p.cost_center
            ORDER BY total_amount DESC
        """)
        return [dict(row) for row in rows]
