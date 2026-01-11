"""
Admin API endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.postgres import get_postgres_session
from app.db.mongodb import get_mongodb
from app.db.redis import get_redis, RedisClient
from app.services.auth_service import AuthService
from app.services.allowance_service import AllowanceService
from app.services.student_service import StudentService
from app.schemas.api_schemas import (
    CreateUserRequest, CreateUserResponse,
    AllowanceResetRequest, AllowanceResetResponse,
    AllowanceBumpRequest, AllowanceBumpResponse,
    ErrorResponse, TokenPayload
)
from app.api.dependencies import require_admin


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/users/create",
    response_model=CreateUserResponse,
    responses={400: {"model": ErrorResponse}}
)
async def create_user(
    request: CreateUserRequest,
    current_user: TokenPayload = Depends(require_admin),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Create a new user in the system.
    For students, also creates the PostgreSQL student record.
    """
    auth_service = AuthService(mongo)
    
    # Create user in MongoDB
    success, message, user_id = await auth_service.create_user(
        email=request.email,
        name=request.name,
        role=request.role,
        password=request.password,
        admin_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # If student, create PostgreSQL record
    if request.role == "student":
        if not request.program_id:
            # Rollback: delete the MongoDB user
            await mongo.users.delete_one({"user_id": user_id})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="program_id is required for student users"
            )
        
        student_service = StudentService(pg, mongo)
        student_success, student_message, student_id = await student_service.create_student_record(
            user_id=user_id,
            full_name=request.name,
            program_id=request.program_id
        )
        
        if not student_success:
            # Rollback: delete the MongoDB user
            await mongo.users.delete_one({"user_id": user_id})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create student record: {student_message}"
            )
    
    return CreateUserResponse(
        success=True,
        user_id=user_id,
        email=request.email,
        role=request.role,
        message=f"User created successfully"
    )


@router.post(
    "/allowance/reset",
    response_model=AllowanceResetResponse,
    responses={400: {"model": ErrorResponse}}
)
async def reset_allowances(
    request: AllowanceResetRequest,
    current_user: TokenPayload = Depends(require_admin),
    pg: AsyncSession = Depends(get_postgres_session),
    redis: RedisClient = Depends(get_redis)
):
    """
    Reset daily allowances.
    If student_id is provided, resets only that student.
    Otherwise, resets all active students.
    """
    service = AllowanceService(pg, redis)
    
    if request.student_id:
        # Reset single student
        success, message = await service.reset_single_allowance(
            admin_id=current_user.user_id,
            student_id=request.student_id,
            base_amount=request.base_amount
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return AllowanceResetResponse(
            success=True,
            students_affected=1,
            date=str(date.today()),
            message=message
        )
    else:
        # Reset all students
        count = await service.reset_all_allowances(
            admin_id=current_user.user_id,
            base_amount=request.base_amount
        )
        
        return AllowanceResetResponse(
            success=True,
            students_affected=count,
            date=str(date.today()),
            message=f"Reset allowances for {count} students"
        )


@router.post(
    "/allowance/bump",
    response_model=AllowanceBumpResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def bump_allowance(
    request: AllowanceBumpRequest,
    current_user: TokenPayload = Depends(require_admin),
    pg: AsyncSession = Depends(get_postgres_session),
    redis: RedisClient = Depends(get_redis)
):
    """
    Add bonus amount to a student's daily allowance.
    """
    service = AllowanceService(pg, redis)
    
    success, message, new_total = await service.bump_allowance(
        admin_id=current_user.user_id,
        student_id=request.student_id,
        bonus_amount=request.bonus_amount
    )
    
    if not success:
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=message)
    
    return AllowanceBumpResponse(
        success=True,
        student_id=request.student_id,
        new_total=new_total,
        message=message
    )


@router.post(
    "/allowance/reset-program",
    responses={400: {"model": ErrorResponse}}
)
async def reset_program_allowances(
    program_id: str = None,
    current_user: TokenPayload = Depends(require_admin),
    pg: AsyncSession = Depends(get_postgres_session),
    redis: RedisClient = Depends(get_redis)
):
    """
    Reset daily allowances for all active students and teachers in active programs.
    Uses each program's default_daily_allowance value.
    If program_id is provided, only resets that program.
    This is designed to be called daily by a cron job or scheduler.
    """
    service = AllowanceService(pg, redis)
    
    result = await service.reset_program_allowances(
        admin_id=current_user.user_id,
        program_id=program_id
    )
    
    return {
        "success": True,
        **result,
        "message": f"Reset allowances for {result['students_reset']} students and {result['teachers_reset']} teachers across {result['programs_processed']} programs"
    }


@router.post(
    "/allowance/teacher/reset",
    responses={400: {"model": ErrorResponse}}
)
async def reset_teacher_allowance(
    teacher_id: str = None,
    base_amount: float = None,
    current_user: TokenPayload = Depends(require_admin),
    pg: AsyncSession = Depends(get_postgres_session),
    redis: RedisClient = Depends(get_redis)
):
    """
    Reset allowance for a single teacher or all teachers.
    """
    from decimal import Decimal
    
    service = AllowanceService(pg, redis)
    
    if teacher_id:
        success, message = await service.reset_single_teacher_allowance(
            admin_id=current_user.user_id,
            teacher_id=teacher_id,
            base_amount=Decimal(str(base_amount)) if base_amount else None
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        return {
            "success": True,
            "teachers_affected": 1,
            "date": str(date.today()),
            "message": message
        }
    else:
        # Reset all teachers
        teachers = await service.get_all_active_teachers()
        count = 0
        amount = Decimal(str(base_amount)) if base_amount else None
        
        for teacher in teachers:
            await service.reset_allowance_for_teacher(
                teacher=teacher,
                base_amount=amount,
                admin_id=current_user.user_id
            )
            count += 1
        
        return {
            "success": True,
            "teachers_affected": count,
            "date": str(date.today()),
            "message": f"Reset allowances for {count} teachers"
        }


@router.post(
    "/allowance/teacher/bump",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def bump_teacher_allowance(
    teacher_id: str,
    bonus_amount: float,
    current_user: TokenPayload = Depends(require_admin),
    pg: AsyncSession = Depends(get_postgres_session),
    redis: RedisClient = Depends(get_redis)
):
    """
    Add bonus amount to a teacher's daily allowance.
    """
    from decimal import Decimal
    
    service = AllowanceService(pg, redis)
    
    success, message, new_total = await service.bump_teacher_allowance(
        admin_id=current_user.user_id,
        teacher_id=teacher_id,
        bonus_amount=Decimal(str(bonus_amount))
    )
    
    if not success:
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=message)
    
    return {
        "success": True,
        "teacher_id": teacher_id,
        "new_total": float(new_total) if new_total else None,
        "message": message
    }
