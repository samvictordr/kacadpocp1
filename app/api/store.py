"""
Store API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres import get_postgres_session
from app.db.mongodb import get_mongodb
from app.db.redis import get_redis, RedisClient
from app.services.store_service import StoreService
from app.schemas.api_schemas import (
    StoreScanRequest, StoreScanResponse,
    StoreChargeRequest, StoreChargeResponse,
    ErrorResponse, TokenPayload
)
from app.api.dependencies import require_store


router = APIRouter(prefix="/store", tags=["Store"])


@router.post(
    "/scan",
    response_model=StoreScanResponse,
    responses={404: {"model": ErrorResponse}}
)
async def scan_student(
    request: StoreScanRequest,
    current_user: TokenPayload = Depends(require_store),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Scan a student's QR code to view their balance.
    """
    service = StoreService(pg, mongo, redis)
    success, message, data = await service.scan_student(
        student_id=request.student_id,
        staff_user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=message
        )
    
    return StoreScanResponse(**data)


@router.post(
    "/charge",
    response_model=StoreChargeResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def charge_student(
    request: StoreChargeRequest,
    current_user: TokenPayload = Depends(require_store),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Charge a student's allowance for a purchase.
    """
    service = StoreService(pg, mongo, redis)
    success, message, data = await service.charge_student(
        staff_user_id=current_user.user_id,
        student_id=request.student_id,
        amount=request.amount,
        location=request.location,
        notes=request.notes
    )
    
    if not success:
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=message)
    
    return StoreChargeResponse(**data)
