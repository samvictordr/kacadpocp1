"""
MongoDB async connection using Motor.
Handles identity, roles, and profiles.

Supports both local MongoDB and MongoDB Atlas (SRV connections).
For Atlas, the MONGODB_URI should be in the format:
mongodb+srv://user:pass@cluster.mongodb.net/dbname?retryWrites=true&w=majority
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.server_api import ServerApi
from typing import Optional
import certifi

from app.core.config import settings


class MongoDB:
    """MongoDB connection manager."""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self) -> None:
        """Connect to MongoDB (supports both local and Atlas)."""
        mongo_url = settings.mongo_url
        
        # Configure connection options
        connection_options = {
            "serverSelectionTimeoutMS": 30000,  # 30 second timeout
            "connectTimeoutMS": 30000,
            "socketTimeoutMS": 30000,
        }
        
        # For MongoDB Atlas (SRV connections), configure TLS properly for Python 3.13
        if mongo_url.startswith("mongodb+srv://"):
            connection_options["server_api"] = ServerApi('1')
            connection_options["tlsCAFile"] = certifi.where()
            # NOTE: If you're getting SSL errors, ensure MongoDB Atlas has 0.0.0.0/0 
            # in the IP Access List (Network Access → Add IP Address → Allow Access from Anywhere)
        
        self.client = AsyncIOMotorClient(mongo_url, **connection_options)
        self.db = self.client[settings.MONGO_DB]
        
        # Verify connection by pinging the database
        await self.client.admin.command('ping')
        
        # Create indexes for the users collection
        await self._create_indexes()
    
    async def _create_indexes(self) -> None:
        """Create required indexes for collections."""
        users = self.db.users
        
        # Unique index on user_id
        await users.create_index("user_id", unique=True)
        
        # Unique index on email
        await users.create_index("email", unique=True)
        
        # Index on role for role-based queries
        await users.create_index("role")
        
        # Index on status
        await users.create_index("status")
        
        # Compound index for login queries
        await users.create_index([("email", 1), ("status", 1)])
    
    async def close(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
    
    @property
    def users(self):
        """Get the users collection."""
        return self.db.users


# Global MongoDB instance
mongodb = MongoDB()


async def get_mongodb() -> AsyncIOMotorDatabase:
    """Dependency that provides the MongoDB database."""
    return mongodb.db


async def init_mongodb() -> None:
    """Initialize MongoDB connection."""
    await mongodb.connect()


async def close_mongodb() -> None:
    """Close MongoDB connection."""
    await mongodb.close()
