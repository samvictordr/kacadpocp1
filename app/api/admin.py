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
