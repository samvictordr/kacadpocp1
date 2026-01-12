"""
Student API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from pydantic import BaseModel

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


# ===== Profile Models =====

class StudentProfileResponse(BaseModel):
    """Student profile response."""
    full_name: str
    email: str
    phone_number: Optional[str] = None
    program_name: Optional[str] = None
    class_name: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    """Request to update student profile."""
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


# ===== Profile Endpoints =====

@router.get(
    "/profile",
    response_model=StudentProfileResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_profile(
    current_user: TokenPayload = Depends(require_student),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Get the current student's profile information.
    """
    # Get user info from MongoDB
    user = await mongo.users.find_one({"user_id": current_user.user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get student details from PostgreSQL
    result = await pg.execute(text("""
        SELECT s.full_name, s.phone_number, p.name as program_name, c.name as class_name
        FROM students s
        LEFT JOIN programs p ON s.program_id = p.program_id
        LEFT JOIN class_enrollments ce ON s.student_id = ce.student_id
        LEFT JOIN classes c ON ce.class_id = c.class_id
        WHERE s.user_id = :user_id
    """), {"user_id": current_user.user_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found"
        )
    
    return StudentProfileResponse(
        full_name=row.full_name,
        email=user.get("email", ""),
        phone_number=row.phone_number,
        program_name=row.program_name,
        class_name=row.class_name
    )


@router.put(
    "/profile",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}
)
async def update_profile(
    data: UpdateProfileRequest,
    current_user: TokenPayload = Depends(require_student),
    pg: AsyncSession = Depends(get_postgres_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongodb)
):
    """
    Update the current student's profile information.
    Students can update their name and phone number.
    """
    # Validate phone number if provided
    if data.phone_number:
        phone = data.phone_number.strip().replace(" ", "").replace("-", "")
        if phone:
            # Validate Saudi phone format
            if phone.startswith("+966"):
                digits = phone[4:]
                if not (len(digits) == 9 and digits.isdigit() and digits[0] == "5"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid phone: must be +966 followed by 9 digits starting with 5"
                    )
            elif phone.startswith("05"):
                if not (len(phone) == 10 and phone.isdigit()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid phone: must be 10 digits starting with 05"
                    )
                phone = "+966" + phone[1:]  # Normalize
            elif phone.startswith("5") and len(phone) == 9 and phone.isdigit():
                phone = "+966" + phone  # Normalize
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid phone format. Use +966XXXXXXXXX or 05XXXXXXXX"
                )
            data.phone_number = phone
    
    # Build update fields
    update_fields = {}
    if data.full_name and data.full_name.strip():
        update_fields["full_name"] = data.full_name.strip()
    if data.phone_number is not None:
        update_fields["phone_number"] = data.phone_number.strip() if data.phone_number else None
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields to update"
        )
    
    # Update PostgreSQL (student record)
    set_clause = ", ".join([f"{k} = :{k}" for k in update_fields])
    update_fields["user_id"] = current_user.user_id
    
    result = await pg.execute(text(f"""
        UPDATE students SET {set_clause} WHERE user_id = :user_id
        RETURNING student_id
    """), update_fields)
    row = result.fetchone()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found"
        )
    
    await pg.commit()
    
    # Also update MongoDB if full_name changed
    if "full_name" in update_fields:
        await mongo.users.update_one(
            {"user_id": current_user.user_id},
            {"$set": {"full_name": update_fields["full_name"]}}
        )
    
    return {"success": True, "message": "Profile updated successfully"}


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
