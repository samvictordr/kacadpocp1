"""
Teacher API endpoints.
"""
from typing import Optional
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

@router.get("/attendance/history")
async def get_attendance_history(
    class_id: Optional[str] = None,
    date: Optional[str] = None,
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session)
):
    """
    Get attendance history for teacher's classes.
    Can filter by class_id and/or date (YYYY-MM-DD format).
    """
    from sqlalchemy import text
    
    # Build query based on filters
    query = """
        SELECT 
            ar.record_id,
            ar.scanned_at,
            ar.status,
            s.full_name as student_name,
            s.student_id,
            c.name as class_name,
            c.class_id,
            asess.date as attendance_date,
            asess.session_id
        FROM attendance_records ar
        JOIN attendance_sessions asess ON ar.session_id = asess.session_id
        JOIN students s ON ar.student_id = s.student_id
        JOIN classes c ON asess.class_id = c.class_id
        WHERE c.teacher_id = :teacher_id
    """
    params = {"teacher_id": current_user.user_id}
    
    if class_id:
        query += " AND c.class_id = :class_id"
        params["class_id"] = class_id
    
    if date:
        query += " AND asess.date = :date"
        params["date"] = date
    
    query += " ORDER BY ar.scanned_at DESC LIMIT 200"
    
    result = await pg.execute(text(query), params)
    records = result.fetchall()
    
    return {
        "records": [
            {
                "record_id": str(r[0]),
                "scanned_at": r[1].isoformat() if r[1] else None,
                "status": r[2],
                "student_name": r[3],
                "student_id": str(r[4]),
                "class_name": r[5],
                "class_id": str(r[6]),
                "attendance_date": str(r[7]),
                "session_id": str(r[8])
            }
            for r in records
        ]
    }


@router.get("/attendance/session/{session_id}")
async def get_session_attendance(
    session_id: str,
    current_user: TokenPayload = Depends(require_teacher),
    pg: AsyncSession = Depends(get_postgres_session)
):
    """
    Get all attendance records for a specific session.
    """
    from sqlalchemy import text
    
    # Verify teacher owns this session
    result = await pg.execute(text("""
        SELECT asess.session_id, asess.date, c.name as class_name, c.class_id
        FROM attendance_sessions asess
        JOIN classes c ON asess.class_id = c.class_id
        WHERE asess.session_id = :session_id AND c.teacher_id = :teacher_id
    """), {"session_id": session_id, "teacher_id": current_user.user_id})
    
    session_info = result.fetchone()
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found or not authorized")
    
    # Get records
    result = await pg.execute(text("""
        SELECT 
            ar.record_id,
            ar.scanned_at,
            ar.status,
            s.full_name as student_name,
            s.student_id
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE ar.session_id = :session_id
        ORDER BY ar.scanned_at ASC
    """), {"session_id": session_id})
    
    records = result.fetchall()
    
    return {
        "session_id": str(session_info[0]),
        "date": str(session_info[1]),
        "class_name": session_info[2],
        "class_id": str(session_info[3]),
        "records": [
            {
                "record_id": str(r[0]),
                "scanned_at": r[1].isoformat() if r[1] else None,
                "status": r[2],
                "student_name": r[3],
                "student_id": str(r[4])
            }
            for r in records
        ],
        "total_present": len(records)
    }