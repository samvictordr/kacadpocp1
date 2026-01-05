"""
Pydantic schemas for API request/response validation.
"""
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
import uuid


# ============ Auth Schemas ============

class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    name: str


class ChangePasswordRequest(BaseModel):
    """Change password request body."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordResponse(BaseModel):
    """Change password response."""
    success: bool
    message: str


# ============ Student Schemas ============

class AttendanceQRResponse(BaseModel):
    """Response containing QR code data for attendance."""
    qr_token: str
    student_id: str
    expires_at: datetime


class StoreQRResponse(BaseModel):
    """Response containing QR code data for store purchases."""
    student_id: str
    date: str
    balance: Decimal


class StudentBalanceResponse(BaseModel):
    """Response containing student's current balance."""
    student_id: str
    date: str
    base_amount: Decimal
    bonus_amount: Decimal
    total_amount: Decimal
    spent_today: Decimal
    remaining: Decimal


# ============ Teacher Schemas ============

class ClassResponse(BaseModel):
    """Class information for teachers."""
    class_id: str
    name: str
    program_id: str
    active: bool


class TeacherClassesResponse(BaseModel):
    """Response with teacher's classes."""
    classes: List[ClassResponse]


class TeacherMealQRResponse(BaseModel):
    """Response containing QR code data for teacher meal purchases."""
    teacher_id: str
    date: str
    balance: Decimal


class TeacherBalanceResponse(BaseModel):
    """Response containing teacher's current meal balance."""
    teacher_id: str
    date: str
    base_amount: Decimal
    bonus_amount: Decimal
    total_amount: Decimal
    spent_today: Decimal
    remaining: Decimal


class AttendanceMode(str, Enum):
    """Mode of attendance session."""
    STATIC = "static"
    DYNAMIC = "dynamic"


class StartAttendanceSessionRequest(BaseModel):
    """Request to start an attendance session."""
    class_id: str
    mode: AttendanceMode = AttendanceMode.STATIC


class StartAttendanceSessionResponse(BaseModel):
    """Response after starting an attendance session."""
    session_id: str
    class_id: str
    date: str
    mode: str
    created_at: datetime


class AttendanceScanRequest(BaseModel):
    """Request to scan a student's attendance QR."""
    qr_token: str
    session_id: str


class AttendanceScanResponse(BaseModel):
    """Response after scanning attendance."""
    success: bool
    student_id: str
    student_name: str
    status: str
    scanned_at: datetime
    message: str


# ============ Store Schemas ============

class StoreScanRequest(BaseModel):
    """Request to scan a student's store QR."""
    student_id: str


class StoreScanResponse(BaseModel):
    """Response after scanning store QR - shows balance."""
    student_id: str
    student_name: str
    program_name: str
    balance: Decimal
    date: str


class StoreChargeRequest(BaseModel):
    """Request to charge a student's allowance."""
    student_id: str
    amount: Decimal = Field(..., gt=0)
    location: Optional[str] = None
    notes: Optional[str] = None


class StoreChargeResponse(BaseModel):
    """Response after charging a student."""
    success: bool
    transaction_id: str
    student_id: str
    amount: Decimal
    balance_after: Decimal
    message: str


# ============ Admin Schemas ============

class CreateUserRequest(BaseModel):
    """Request to create a new user."""
    email: EmailStr
    name: str
    role: str = Field(..., pattern="^(student|teacher|store|admin)$")
    password: str = Field(..., min_length=8)
    program_id: Optional[str] = None  # Required for students


class CreateUserResponse(BaseModel):
    """Response after creating a user."""
    success: bool
    user_id: str
    email: str
    role: str
    message: str


class AllowanceResetRequest(BaseModel):
    """Request to reset allowances."""
    student_id: Optional[str] = None  # If None, reset all
    base_amount: Optional[Decimal] = None  # If None, use default


class AllowanceResetResponse(BaseModel):
    """Response after resetting allowances."""
    success: bool
    students_affected: int
    date: str
    message: str


class AllowanceBumpRequest(BaseModel):
    """Request to add bonus to a student's allowance."""
    student_id: str
    bonus_amount: Decimal = Field(..., gt=0)


class AllowanceBumpResponse(BaseModel):
    """Response after bumping allowance."""
    success: bool
    student_id: str
    new_total: Decimal
    message: str


# ============ Common Schemas ============

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str
    user_id: str
    role: str
    exp: datetime
    iat: datetime
