"""
Allowance service.
Handles daily allowance management, resets, and bumps.
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.postgres_models import Student, DailyAllowance
from app.db.redis import RedisClient
from app.core.config import settings
from app.core.logging import audit_log


class AllowanceService:
    """Service for allowance management operations."""
    
    def __init__(self, pg_session: AsyncSession, redis: RedisClient):
        self.pg = pg_session
        self.redis = redis
    
    async def get_all_active_students(self) -> List[Student]:
        """Get all active students."""
        result = await self.pg.execute(
            select(Student).where(Student.is_active == True)
        )
        return result.scalars().all()
    
    async def get_student_by_id(self, student_id: str) -> Optional[Student]:
        """Get a student by ID."""
        result = await self.pg.execute(
            select(Student).where(Student.student_id == UUID(student_id))
        )
        return result.scalar_one_or_none()
    
    async def reset_allowance_for_student(
        self,
        student: Student,
        base_amount: Optional[Decimal] = None,
        admin_id: Optional[str] = None
    ) -> DailyAllowance:
        """
        Reset or create today's allowance for a single student.
        """
        today = date.today()
        amount = base_amount if base_amount is not None else Decimal(str(settings.DEFAULT_DAILY_ALLOWANCE))
        
        # Check if allowance exists for today
        result = await self.pg.execute(
            select(DailyAllowance).where(
                DailyAllowance.student_id == student.student_id,
                DailyAllowance.date == today
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing allowance
            existing.base_amount = amount
            existing.total_amount = amount + existing.bonus_amount
            existing.reset_at = datetime.now(timezone.utc)
            allowance = existing
        else:
            # Create new allowance
            allowance = DailyAllowance(
                student_id=student.student_id,
                date=today,
                base_amount=amount,
                bonus_amount=Decimal("0.00"),
                total_amount=amount
            )
            self.pg.add(allowance)
        
        await self.pg.flush()
        
        # Update Redis cache
        await self.redis.set_store_token(
            student_id=str(student.student_id),
            date=str(today),
            balance=allowance.total_amount
        )
        
        return allowance
    
    async def reset_all_allowances(
        self,
        admin_id: str,
        base_amount: Optional[Decimal] = None
    ) -> int:
        """
        Reset allowances for all active students.
        Returns the number of students affected.
        """
        students = await self.get_all_active_students()
        count = 0
        
        for student in students:
            await self.reset_allowance_for_student(
                student=student,
                base_amount=base_amount,
                admin_id=admin_id
            )
            count += 1
        
        audit_log.log_allowance_reset(admin_id=admin_id, scope="all")
        
        return count
    
    async def reset_single_allowance(
        self,
        admin_id: str,
        student_id: str,
        base_amount: Optional[Decimal] = None
    ) -> tuple[bool, str]:
        """
        Reset allowance for a single student.
        Returns (success, message).
        """
        student = await self.get_student_by_id(student_id)
        if not student:
            return False, "Student not found"
        
        if not student.is_active:
            return False, "Student is inactive"
        
        await self.reset_allowance_for_student(
            student=student,
            base_amount=base_amount,
            admin_id=admin_id
        )
        
        audit_log.log_allowance_reset(
            admin_id=admin_id,
            target_id=student_id,
            scope="single"
        )
        
        return True, "Allowance reset successfully"
    
    async def bump_allowance(
        self,
        admin_id: str,
        student_id: str,
        bonus_amount: Decimal
    ) -> tuple[bool, str, Optional[Decimal]]:
        """
        Add bonus to a student's daily allowance.
        Returns (success, message, new_total).
        """
        student = await self.get_student_by_id(student_id)
        if not student:
            return False, "Student not found", None
        
        if not student.is_active:
            return False, "Student is inactive", None
        
        today = date.today()
        
        # Get today's allowance
        result = await self.pg.execute(
            select(DailyAllowance).where(
                DailyAllowance.student_id == student.student_id,
                DailyAllowance.date == today
            )
        )
        allowance = result.scalar_one_or_none()
        
        if not allowance:
            # Create allowance first
            allowance = await self.reset_allowance_for_student(student, admin_id=admin_id)
        
        # Add bonus
        allowance.bonus_amount += bonus_amount
        allowance.total_amount = allowance.base_amount + allowance.bonus_amount
        
        await self.pg.flush()
        
        # Update Redis cache
        await self.redis.set_store_token(
            student_id=str(student.student_id),
            date=str(today),
            balance=allowance.total_amount
        )
        
        audit_log.info(
            "admin.allowance.bump",
            actor_id=admin_id,
            actor_role="admin",
            target_type="student",
            target_id=student_id,
            details={"bonus_amount": bonus_amount, "new_total": allowance.total_amount}
        )
        
        return True, "Bonus added successfully", allowance.total_amount
