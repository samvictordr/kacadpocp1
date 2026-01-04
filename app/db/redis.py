"""
Redis async connection using redis-py.
Handles ephemeral QR tokens with TTL-based expiration.
Redis must NEVER be the system of record.

Supports both local Redis and Render Redis (with TLS via rediss://).
"""
import redis.asyncio as redis
import ssl
from typing import Optional, Any, Union
from decimal import Decimal
import json
from datetime import datetime, timezone

from app.core.config import settings


class RedisClient:
    """Redis connection manager for ephemeral tokens."""
    
    client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis (supports both local and Render with TLS)."""
        redis_url = settings.redis_url_resolved
        
        # Configure connection options
        connection_options = {
            "encoding": "utf-8",
            "decode_responses": True,
            "socket_timeout": 30.0,
            "socket_connect_timeout": 10.0,
        }
        
        # Handle TLS for Render Redis (rediss:// scheme)
        if settings.redis_ssl_enabled:
            # Create SSL context for TLS connections
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            connection_options["ssl"] = ssl_context
        
        self.client = redis.from_url(redis_url, **connection_options)
        
        # Test connection
        await self.client.ping()
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()
    
    # Attendance QR Token Methods
    async def set_attendance_token(
        self,
        token: str,
        student_id: str,
        class_id: str,
        session_id: str,
        expires_at: datetime
    ) -> None:
        """
        Store an attendance QR token.
        Key: attendance:{token}
        TTL: 24 hours
        """
        key = f"attendance:{token}"
        value = {
            "student_id": student_id,
            "class_id": class_id,
            "session_id": session_id,
            "expires_at": expires_at.isoformat(),
            "used": False
        }
        await self.client.setex(
            key,
            settings.ATTENDANCE_QR_TTL,
            json.dumps(value)
        )
    
    async def get_attendance_token(self, token: str) -> Optional[dict[str, Any]]:
        """Retrieve an attendance token."""
        key = f"attendance:{token}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def mark_attendance_token_used(self, token: str) -> bool:
        """Mark an attendance token as used."""
        key = f"attendance:{token}"
        data = await self.client.get(key)
        if data:
            token_data = json.loads(data)
            token_data["used"] = True
            ttl = await self.client.ttl(key)
            if ttl > 0:
                await self.client.setex(key, ttl, json.dumps(token_data))
                return True
        return False
    
    async def delete_attendance_token(self, token: str) -> None:
        """Delete an attendance token."""
        key = f"attendance:{token}"
        await self.client.delete(key)
    
    # Store Allowance Token Methods
    async def set_store_token(
        self,
        student_id: str,
        date: str,
        balance: Union[Decimal, float],
        last_transaction_at: Optional[datetime] = None
    ) -> None:
        """
        Store/update a store allowance token.
        Key: store:{student_id}:{date}
        TTL: 24 hours
        """
        key = f"store:{student_id}:{date}"
        value = {
            "balance": str(balance),  # Store as string to preserve precision
            "last_transaction_at": last_transaction_at.isoformat() if last_transaction_at else None
        }
        await self.client.setex(
            key,
            settings.STORE_TOKEN_TTL,
            json.dumps(value)
        )
    
    async def get_store_token(self, student_id: str, date: str) -> Optional[dict[str, Any]]:
        """Retrieve a store allowance token."""
        key = f"store:{student_id}:{date}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def update_store_balance(
        self,
        student_id: str,
        date: str,
        new_balance: Union[Decimal, float]
    ) -> bool:
        """Update the balance in a store token."""
        key = f"store:{student_id}:{date}"
        data = await self.client.get(key)
        if data:
            token_data = json.loads(data)
            token_data["balance"] = str(new_balance)  # Store as string to preserve precision
            token_data["last_transaction_at"] = datetime.now(timezone.utc).isoformat()
            ttl = await self.client.ttl(key)
            if ttl > 0:
                await self.client.setex(key, ttl, json.dumps(token_data))
                return True
        return False
    
    async def delete_store_token(self, student_id: str, date: str) -> None:
        """Delete a store token."""
        key = f"store:{student_id}:{date}"
        await self.client.delete(key)


# Global Redis instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency that provides the Redis client."""
    return redis_client


async def init_redis() -> None:
    """Initialize Redis connection."""
    await redis_client.connect()


async def close_redis() -> None:
    """Close Redis connection."""
    await redis_client.close()
