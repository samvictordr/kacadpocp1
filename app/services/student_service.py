"""
Student service.
Handles student-specific operations and PostgreSQL record management.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.postgres_models import Student, Program
from app.core.logging import audit_log


class StudentService:
    """Service for student management operations."""
    
    def __init__(self, pg_session: AsyncSession, mongo_db: AsyncIOMotorDatabase):
        self.pg = pg_session
        self.mongo = mongo_db
    
    async def create_student_record(
        self,
        user_id: str,
        full_name: str,
        program_id: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Create a student record in PostgreSQL.
        This links the MongoDB user to the PostgreSQL student.
        Returns (success, message, student_id).
        """
        # Check if student already exists
        result = await self.pg.execute(
            select(Student).where(Student.user_id == UUID(user_id))
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return False, "Student record already exists", None
        
        # Verify program exists
        result = await self.pg.execute(
            select(Program).where(Program.program_id == UUID(program_id))
        )
        program = result.scalar_one_or_none()
        
        if not program:
            return False, "Program not found", None
        
        if not program.active:
            return False, "Program is not active", None
        
        # Create student
        student = Student(
            user_id=UUID(user_id),
            full_name=full_name,
            program_id=UUID(program_id)
        )
        
        self.pg.add(student)
        await self.pg.flush()
        
        # Update MongoDB user associations
        await self.mongo.users.update_one(
            {"user_id": user_id},
            {"$addToSet": {"associations.programs": program_id}}
        )
        
        audit_log.info(
            "student.record.created",
            target_type="student",
            target_id=str(student.student_id),
            details={"user_id": user_id, "program_id": program_id}
        )
        
        return True, "Student record created", str(student.student_id)
    
    async def get_student_by_user_id(self, user_id: str) -> Optional[Student]:
        """Get student by user_id."""
        result = await self.pg.execute(
            select(Student).where(Student.user_id == UUID(user_id))
        )
        return result.scalar_one_or_none()
    
    async def get_student_with_program(self, user_id: str) -> Optional[dict]:
        """Get student with program info."""
        result = await self.pg.execute(
            select(Student, Program)
            .join(Program)
            .where(Student.user_id == UUID(user_id))
        )
        row = result.one_or_none()
        
        if not row:
            return None
        
        student, program = row
        return {
            "student_id": str(student.student_id),
            "user_id": str(student.user_id),
            "full_name": student.full_name,
            "program_id": str(program.program_id),
            "program_name": program.name,
            "is_active": student.is_active
        }
