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
async def scan_person(
    request: StoreScanRequest,
    current_user: TokenPayload = Depends(require_store),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Scan a student's or teacher's QR code to view their balance.
    Teacher IDs are prefixed with 'teacher:'.
    """
    service = StoreService(pg, mongo, redis)
    person_id = request.student_id
    
    # Check if it's a teacher ID (prefixed with "teacher:")
    if person_id.startswith("teacher:"):
        teacher_id = person_id.replace("teacher:", "")
        success, message, data = await service.scan_teacher(
            teacher_id=teacher_id,
            staff_user_id=current_user.user_id
        )
    else:
        # Try as student first
        success, message, data = await service.scan_student(
            student_id=person_id,
            staff_user_id=current_user.user_id
        )
        
        # If student not found, try as teacher
        if not success:
            success, message, data = await service.scan_teacher(
                teacher_id=person_id,
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
async def charge_person(
    request: StoreChargeRequest,
    current_user: TokenPayload = Depends(require_store),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Charge a student's or teacher's allowance for a purchase.
    Teacher IDs are prefixed with 'teacher:'.
    """
    service = StoreService(pg, mongo, redis)
    person_id = request.student_id
    
    # Check if it's a teacher
    if person_id.startswith("teacher:"):
        teacher_id = person_id.replace("teacher:", "")
        success, message, data = await service.charge_teacher(
            staff_user_id=current_user.user_id,
            teacher_id=teacher_id,
            amount=request.amount,
            location=request.location,
            notes=request.notes
        )
    else:
        success, message, data = await service.charge_student(
            staff_user_id=current_user.user_id,
            student_id=person_id,
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
