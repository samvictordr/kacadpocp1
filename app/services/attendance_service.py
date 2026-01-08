"""
Attendance service.
Handles attendance sessions, QR token generation, and scanning.
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.postgres_models import (
    AttendanceSession, AttendanceRecord, AttendanceMode, AttendanceStatus,
    Class, ClassEnrollment, Student
)
from app.db.redis import RedisClient
from app.core.security import generate_qr_token
from app.core.config import settings
from app.core.logging import audit_log


class AttendanceService:
    """Service for attendance operations."""
    
    def __init__(
        self,
        pg_session: AsyncSession,
        mongo_db: AsyncIOMotorDatabase,
        redis: RedisClient
    ):
        self.pg = pg_session
        self.mongo = mongo_db
        self.redis = redis
    
    async def get_student_by_user_id(self, user_id: str) -> Optional[Student]:
        """Get student record by user_id."""
        result = await self.pg.execute(
            select(Student).where(Student.user_id == UUID(user_id))
        )
        return result.scalar_one_or_none()
    
    async def get_student_classes(self, student_id: UUID) -> List[Class]:
        """Get all classes a student is enrolled in."""
        result = await self.pg.execute(
            select(Class)
            .join(ClassEnrollment)
            .where(ClassEnrollment.student_id == student_id)
            .where(Class.active == True)
        )
        return result.scalars().all()
    
    async def get_active_session_for_class(self, class_id: UUID) -> Optional[AttendanceSession]:
        """Get the active (unclosed) session for a class today."""
        today = date.today()
        result = await self.pg.execute(
            select(AttendanceSession)
            .where(AttendanceSession.class_id == class_id)
            .where(AttendanceSession.date == today)
            .where(AttendanceSession.closed_at == None)
        )
        return result.scalar_one_or_none()
    
    async def generate_attendance_qr(self, user_id: str) -> Optional[dict]:
        """
        Generate an attendance QR token for a student.
        The token is stored in Redis with TTL.
        """
        student = await self.get_student_by_user_id(user_id)
        if not student:
            return None
        
        # Get enrolled classes
        classes = await self.get_student_classes(student.student_id)
        if not classes:
            return None
        
        # Find active session in any enrolled class
        active_session = None
        target_class = None
        for cls in classes:
            session = await self.get_active_session_for_class(cls.class_id)
            if session:
                active_session = session
                target_class = cls
                break
        
        if not active_session:
            # No active session, still generate token for potential future use
            target_class = classes[0]
            session_id = "pending"
        else:
            session_id = str(active_session.session_id)
        
        # Generate QR token
        token = generate_qr_token()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.ATTENDANCE_QR_TTL)
        
        # Store in Redis
        await self.redis.set_attendance_token(
            token=token,
            student_id=str(student.student_id),
            class_id=str(target_class.class_id),
            session_id=session_id,
            expires_at=expires_at
        )
        
        return {
            "qr_token": token,
            "student_id": str(student.student_id),
            "expires_at": expires_at
        }
    
    async def start_attendance_session(
        self,
        teacher_user_id: str,
        class_id: str,
        mode: str
    ) -> Optional[dict]:
        """
        Start a new attendance session for a class.
        Only the assigned teacher can start a session.
        """
        # Verify teacher owns this class
        result = await self.pg.execute(
            select(Class).where(
                Class.class_id == UUID(class_id),
                Class.teacher_id == UUID(teacher_user_id),
                Class.active == True
            )
        )
        class_obj = result.scalar_one_or_none()
        
        if not class_obj:
            return None
        
        # Check for existing active session
        existing = await self.get_active_session_for_class(UUID(class_id))
        if existing:
            # Return existing session
            mode_value = existing.mode.value if hasattr(existing.mode, 'value') else str(existing.mode)
            return {
                "session_id": str(existing.session_id),
                "class_id": str(existing.class_id),
                "date": str(existing.date),
                "mode": mode_value,
                "created_at": existing.created_at
            }
        
        # Create new session
        session = AttendanceSession(
            class_id=UUID(class_id),
            date=date.today(),
            mode=mode,  # Pass the mode string directly (e.g., 'static')
            created_by=UUID(teacher_user_id)
        )
        
        self.pg.add(session)
        await self.pg.flush()
        
        audit_log.info(
            "attendance.session.started",
            actor_id=teacher_user_id,
            actor_role="teacher",
            target_type="class",
            target_id=class_id,
            details={"session_id": str(session.session_id), "mode": mode}
        )
        
        mode_value = session.mode.value if hasattr(session.mode, 'value') else str(session.mode)
        return {
            "session_id": str(session.session_id),
            "class_id": str(session.class_id),
            "date": str(session.date),
            "mode": mode_value,
            "created_at": session.created_at
        }
    
    async def scan_attendance(
        self,
        teacher_user_id: str,
        qr_token: str,
        session_id: str
    ) -> tuple[bool, str, Optional[dict]]:
        """
        Scan a student's attendance QR code.
        Returns (success, message, record_data).
        """
        # Verify session belongs to teacher
        result = await self.pg.execute(
            select(AttendanceSession)
            .join(Class)
            .where(
                AttendanceSession.session_id == UUID(session_id),
                Class.teacher_id == UUID(teacher_user_id),
                AttendanceSession.closed_at == None
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return False, "Invalid or closed session", None
        
        # Get token from Redis
        token_data = await self.redis.get_attendance_token(qr_token)
        if not token_data:
            return False, "Invalid or expired QR token", None
        
        if token_data.get("used"):
            return False, "QR token already used", None
        
        student_id = token_data["student_id"]
        
        # Verify student is enrolled in this class
        result = await self.pg.execute(
            select(ClassEnrollment).where(
                ClassEnrollment.class_id == session.class_id,
                ClassEnrollment.student_id == UUID(student_id)
            )
        )
        enrollment = result.scalar_one_or_none()
        
        if not enrollment:
            return False, "Student not enrolled in this class", None
        
        # Check for duplicate attendance
        result = await self.pg.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == session.session_id,
                AttendanceRecord.student_id == UUID(student_id)
            )
        )
        existing_record = result.scalar_one_or_none()
        
        if existing_record:
            return False, "Attendance already recorded for this session", None
        
        # Get student info
        result = await self.pg.execute(
            select(Student).where(Student.student_id == UUID(student_id))
        )
        student = result.scalar_one_or_none()
        
        if not student:
            return False, "Student not found", None
        
        # Create attendance record
        record = AttendanceRecord(
            session_id=session.session_id,
            student_id=UUID(student_id),
            scanned_by=UUID(teacher_user_id),
            status=AttendanceStatus.PRESENT
        )
        
        self.pg.add(record)
        await self.pg.flush()
        
        # Delete token after successful use (single-use token)
        await self.redis.delete_attendance_token(qr_token)
        
        audit_log.log_attendance_scan(
            teacher_id=teacher_user_id,
            student_id=student_id,
            session_id=session_id,
            status="present"
        )
        
        return True, "Attendance recorded", {
            "success": True,
            "student_id": student_id,
            "student_name": student.full_name,
            "status": "present",
            "scanned_at": record.scanned_at,
            "message": f"Attendance recorded for {student.full_name}"
        }
