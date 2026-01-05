"""
Student API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres import get_postgres_session
from app.db.mongodb import get_mongodb
from app.db.redis import get_redis, RedisClient
from app.services.attendance_service import AttendanceService
from app.services.store_service import StoreService
from app.schemas.api_schemas import (
    AttendanceQRResponse, StoreQRResponse, StudentBalanceResponse,
    ErrorResponse, TokenPayload
)
from app.api.dependencies import require_student


router = APIRouter(prefix="/student", tags=["Student"])


@router.get(
    "/attendance-qr",
    response_model=AttendanceQRResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_attendance_qr(
    current_user: TokenPayload = Depends(require_student),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Generate a QR code token for attendance scanning.
    The token is valid for 24 hours.
    """
    service = AttendanceService(pg, mongo, redis)
    result = await service.generate_attendance_qr(current_user.user_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found or no enrolled classes"
        )
    
    return AttendanceQRResponse(**result)


@router.get(
    "/store-qr",
    response_model=StoreQRResponse,
    responses={404: {"model": ErrorResponse}},
    deprecated=True
)
async def get_store_qr(
    current_user: TokenPayload = Depends(require_student),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    [DEPRECATED] Use /meal-qr instead.
    Get QR code data for store purchases.
    Shows current balance.
    """
    service = StoreService(pg, mongo, redis)
    result = await service.generate_store_qr(current_user.user_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found or no allowance set"
        )
    
    return StoreQRResponse(**result)


@router.get(
    "/meal-qr",
    response_model=StoreQRResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_meal_qr(
    current_user: TokenPayload = Depends(require_student),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get QR code data for meal purchases.
    Shows current balance.
    """
    service = StoreService(pg, mongo, redis)
    result = await service.generate_store_qr(current_user.user_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found or no allowance set"
        )
    
    return StoreQRResponse(**result)


@router.get(
    "/balance",
    response_model=StudentBalanceResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_balance(
    current_user: TokenPayload = Depends(require_student),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get the student's current balance for today.
    """
    service = StoreService(pg, mongo, redis)
    student = await service.get_student_by_user_id(current_user.user_id)
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found"
        )
    
    balance = await service.get_balance(student.student_id)
    
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No allowance set for today"
        )
    
    return StudentBalanceResponse(**balance)
