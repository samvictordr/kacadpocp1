"""
Authentication service.
Handles login, password management, and user retrieval from MongoDB.
"""
from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.mongo_models import UserDocument, UserInDB, UserRole, UserStatus, UserAuth, UserMetadata, UserAssociations
from app.core.security import hash_password, verify_password, create_access_token
from app.core.logging import audit_log


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users = db.users
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by email."""
        doc = await self.users.find_one({"email": email})
        if doc:
            return UserInDB.from_mongo(doc)
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Get a user by user_id."""
        doc = await self.users.find_one({"user_id": user_id})
        if doc:
            return UserInDB.from_mongo(doc)
        return None
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        """
        Authenticate a user with email and password.
        Returns the user if authentication succeeds, None otherwise.
        """
        user = await self.get_user_by_email(email)
        
        if not user:
            audit_log.info("auth.login.user_not_found", details={"email": email})
            return None
        
        if user.status not in [UserStatus.ACTIVE.value, UserStatus.UNINITIALISED.value]:
            audit_log.info(
                "auth.login.inactive_user",
                actor_id=user.user_id,
                details={"status": user.status}
            )
            return None
        
        if not verify_password(password, user.auth["password_hash"]):
            audit_log.log_login(user.user_id, user.role, success=False)
            return None
        
        # Update last login
        await self.users.update_one(
            {"user_id": user.user_id},
            {"$set": {"metadata.last_login": datetime.now(timezone.utc)}}
        )
        
        audit_log.log_login(user.user_id, user.role, success=True)
        return user
    
    async def login(self, email: str, password: str) -> Optional[dict]:
        """
        Full login flow: authenticate and return token.
        """
        user = await self.authenticate_user(email, password)
        
        if not user:
            return None
        
        access_token = create_access_token(
            subject=user.email,
            user_id=user.user_id,
            role=user.role
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.user_id,
            "role": user.role,
            "name": user.name
        }
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> tuple[bool, str]:
        """
        Change a user's password.
        Returns (success, message).
        """
        user = await self.get_user_by_id(user_id)
        
        if not user:
            return False, "User not found"
        
        if not verify_password(current_password, user.auth["password_hash"]):
            audit_log.warning(
                "auth.password.change_failed",
                actor_id=user_id,
                details={"reason": "incorrect_current_password"}
            )
            return False, "Current password is incorrect"
        
        new_hash = hash_password(new_password)
        now = datetime.now(timezone.utc)
        
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "auth.password_hash": new_hash,
                    "auth.password_last_changed": now,
                    "status": UserStatus.ACTIVE.value  # Activate if uninitialised
                }
            }
        )
        
        audit_log.log_password_change(user_id, user.role)
        return True, "Password changed successfully"
    
    async def create_user(
        self,
        email: str,
        name: str,
        role: str,
        password: str,
        admin_id: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Create a new user.
        Returns (success, message, user_id).
        """
        # Check if email already exists
        existing = await self.users.find_one({"email": email})
        if existing:
            return False, "Email already registered", None
        
        now = datetime.now(timezone.utc)
        
        user_doc = UserDocument(
            email=email,
            name=name,
            role=UserRole(role),
            status=UserStatus.UNINITIALISED,
            auth=UserAuth(
                password_hash=hash_password(password),
                password_last_changed=now
            ),
            associations=UserAssociations(),
            metadata=UserMetadata(created_at=now)
        )
        
        await self.users.insert_one(user_doc.model_dump())
        
        audit_log.log_user_created(admin_id, user_doc.user_id, role)
        
        return True, "User created successfully", user_doc.user_id
