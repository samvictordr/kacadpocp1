"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_mongodb
from app.services.auth_service import AuthService
from app.schemas.api_schemas import (
    LoginRequest, LoginResponse,
    ChangePasswordRequest, ChangePasswordResponse,
    ErrorResponse, TokenPayload
)
from app.api.dependencies import get_current_user


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}}
)
async def login(
    request: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Authenticate user and return JWT token.
    """
    auth_service = AuthService(db)
    result = await auth_service.login(request.email, request.password)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    return LoginResponse(**result)


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}}
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Change the current user's password.
    """
    auth_service = AuthService(db)
    success, message = await auth_service.change_password(
        user_id=current_user.user_id,
        current_password=request.current_password,
        new_password=request.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return ChangePasswordResponse(success=True, message=message)
