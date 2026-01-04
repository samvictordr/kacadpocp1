"""
Authentication dependencies for FastAPI.
Provides JWT token validation and role-based access control.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

from app.core.security import decode_token
from app.schemas.api_schemas import TokenPayload


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenPayload:
    """
    Validate JWT token and return current user payload.
    Raises HTTPException if token is invalid.
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return TokenPayload(**payload)


def require_roles(allowed_roles: List[str]):
    """
    Dependency factory for role-based access control.
    Returns a dependency that checks if user has required role.
    """
    async def role_checker(
        current_user: TokenPayload = Depends(get_current_user)
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {allowed_roles}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for specific roles
require_student = require_roles(["student"])
require_teacher = require_roles(["teacher"])
require_store = require_roles(["store"])
require_admin = require_roles(["admin"])
require_teacher_or_admin = require_roles(["teacher", "admin"])
