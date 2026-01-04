"""
MongoDB document models.
These define the structure of documents in MongoDB collections.
Identity, roles, and profiles are stored in MongoDB.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class UserRole(str, Enum):
    """User roles in the system."""
    STUDENT = "student"
    TEACHER = "teacher"
    STORE = "store"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """User account status."""
    UNINITIALISED = "uninitialised"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class UserAuth(BaseModel):
    """Authentication data embedded in user document."""
    password_hash: str
    password_last_changed: datetime


class UserAssociations(BaseModel):
    """User associations with classes and programs."""
    classes: List[str] = Field(default_factory=list)  # List of class_ids
    programs: List[str] = Field(default_factory=list)  # List of program_ids


class UserMetadata(BaseModel):
    """User metadata."""
    created_at: datetime
    last_login: Optional[datetime] = None


class UserDocument(BaseModel):
    """
    Complete user document for MongoDB.
    This is the authoritative source for identity and authentication.
    """
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    role: UserRole
    status: UserStatus = UserStatus.UNINITIALISED
    auth: UserAuth
    associations: UserAssociations = Field(default_factory=UserAssociations)
    metadata: UserMetadata
    
    class Config:
        use_enum_values = True


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr
    name: str
    role: UserRole
    password: str  # Plain text, will be hashed
    
    class Config:
        use_enum_values = True


class UserInDB(BaseModel):
    """User as stored in database (for internal use)."""
    user_id: str
    email: str
    name: str
    role: str
    status: str
    auth: dict
    associations: dict
    metadata: dict
    
    @classmethod
    def from_mongo(cls, doc: dict) -> "UserInDB":
        """Create UserInDB from MongoDB document."""
        if doc is None:
            return None
        return cls(
            user_id=doc["user_id"],
            email=doc["email"],
            name=doc["name"],
            role=doc["role"],
            status=doc["status"],
            auth=doc["auth"],
            associations=doc["associations"],
            metadata=doc["metadata"]
        )
