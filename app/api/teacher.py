"""
Teacher API endpoints.
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
    StartAttendanceSessionRequest, StartAttendanceSessionResponse,
    AttendanceScanRequest, AttendanceScanResponse,
    ClassResponse, TeacherClassesResponse,
    TeacherMealQRResponse, TeacherBalanceResponse,
    ErrorResponse, TokenPayload
)
from app.api.dependencies import require_teacher
from app.models.postgres_models import Class
from sqlalchemy import select
from uuid import UUID


router = APIRouter(prefix="/teacher", tags=["Teacher"])


@router.get(
    "/classes",
    response_model=TeacherClassesResponse,
    responses={401: {"model": ErrorResponse}}
)
async def get_teacher_classes(
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session)
):
    """
    Get all classes assigned to the current teacher.
    """
    result = await pg.execute(
        select(Class).where(
            Class.teacher_id == UUID(current_user.user_id),
            Class.active == True
        )
    )
    classes = result.scalars().all()
    
    return TeacherClassesResponse(
        classes=[
            ClassResponse(
                class_id=str(c.class_id),
                name=c.name,
                program_id=str(c.program_id),
                active=c.active
            )
            for c in classes
        ]
    )


@router.post(
    "/attendance-session/start",
    response_model=StartAttendanceSessionResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}
)
async def start_attendance_session(
    request: StartAttendanceSessionRequest,
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Start a new attendance session for a class.
    Only the assigned teacher can start a session.
    """
    service = AttendanceService(pg, mongo, redis)
    result = await service.start_attendance_session(
        teacher_user_id=current_user.user_id,
        class_id=request.class_id,
        mode=request.mode.value
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Class not found or you are not the assigned teacher"
        )
    
    return StartAttendanceSessionResponse(**result)


@router.post(
    "/attendance/scan",
    response_model=AttendanceScanResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def scan_attendance(
    request: AttendanceScanRequest,
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Scan a student's attendance QR code.
    Records the student as present.
    """
    service = AttendanceService(pg, mongo, redis)
    success, message, data = await service.scan_attendance(
        teacher_user_id=current_user.user_id,
        qr_token=request.qr_token,
        session_id=request.session_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return AttendanceScanResponse(**data)


@router.get(
    "/meal-qr",
    response_model=TeacherMealQRResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_meal_qr(
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get QR code data for teacher meal purchases.
    Shows current balance.
    """
    service = StoreService(pg, mongo, redis)
    result = await service.generate_teacher_meal_qr(current_user.user_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher record not found or no meal allowance set"
        )
    
    return TeacherMealQRResponse(**result)


@router.get(
    "/balance",
    response_model=TeacherBalanceResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_balance(
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: RedisClient = Depends(get_redis)
):
    """
    Get the teacher's current meal balance for today.
    """
    service = StoreService(pg, mongo, redis)
    teacher = await service.get_teacher_by_user_id(current_user.user_id)
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher record not found"
        )
    
    balance = await service.get_teacher_balance(teacher.teacher_id)
    
    if not balance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No meal allowance set for today"
        )
    
    return TeacherBalanceResponse(**balance)
