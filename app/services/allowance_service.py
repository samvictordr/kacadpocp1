"""
Allowance service.
Handles daily allowance management, resets, and bumps.
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text

from app.models.postgres_models import Student, DailyAllowance, Teacher, TeacherDailyAllowance, Program
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

    async def reset_allowance_for_teacher(
        self,
        teacher: Teacher,
        base_amount: Optional[Decimal] = None,
        admin_id: Optional[str] = None
    ) -> TeacherDailyAllowance:
        """
        Reset or create today's allowance for a single teacher.
        """
        today = date.today()
        amount = base_amount if base_amount is not None else Decimal(str(settings.DEFAULT_DAILY_ALLOWANCE))
        
        # Check if allowance exists for today
        result = await self.pg.execute(
            select(TeacherDailyAllowance).where(
                TeacherDailyAllowance.teacher_id == teacher.teacher_id,
                TeacherDailyAllowance.date == today
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
            allowance = TeacherDailyAllowance(
                teacher_id=teacher.teacher_id,
                date=today,
                base_amount=amount,
                bonus_amount=Decimal("0.00"),
                total_amount=amount
            )
            self.pg.add(allowance)
        
        await self.pg.flush()
        
        # Update Redis cache for teacher
        await self.redis.set_store_token(
            student_id=f"teacher_{teacher.teacher_id}",
            date=str(today),
            balance=allowance.total_amount
        )
        
        return allowance

    async def reset_program_allowances(
        self,
        admin_id: str,
        program_id: Optional[str] = None
    ) -> dict:
        """
        Reset allowances for all active students and teachers in active programs.
        Uses each program's default_daily_allowance value.
        If program_id is provided, only resets that program.
        Returns dict with counts.
        """
        today = date.today()
        
        # Get active programs (within date range if start/end dates set)
        query = text("""
            SELECT program_id, name, default_daily_allowance 
            FROM programs 
            WHERE (is_active = true OR active = true)
            AND (start_date IS NULL OR start_date <= :today)
            AND (end_date IS NULL OR end_date >= :today)
        """)
        
        if program_id:
            query = text("""
                SELECT program_id, name, default_daily_allowance 
                FROM programs 
                WHERE program_id = :program_id
                AND (is_active = true OR active = true)
            """)
        
        params = {"today": today}
        if program_id:
            params["program_id"] = program_id
        
        result = await self.pg.execute(query, params)
        programs = result.fetchall()
        
        student_count = 0
        teacher_count = 0
        program_count = 0
        
        for program in programs:
            prog_id, prog_name, default_allowance = program
            if default_allowance is None:
                default_allowance = Decimal(str(settings.DEFAULT_DAILY_ALLOWANCE))
            else:
                default_allowance = Decimal(str(default_allowance))
            
            # Reset student allowances for this program
            student_result = await self.pg.execute(
                select(Student).where(
                    Student.program_id == prog_id,
                    Student.is_active == True
                )
            )
            students = student_result.scalars().all()
            
            for student in students:
                await self.reset_allowance_for_student(
                    student=student,
                    base_amount=default_allowance,
                    admin_id=admin_id
                )
                student_count += 1
            
            # Reset teacher allowances for this program  
            teacher_result = await self.pg.execute(
                select(Teacher).where(
                    Teacher.program_id == prog_id,
                    Teacher.is_active == True
                )
            )
            teachers = teacher_result.scalars().all()
            
            for teacher in teachers:
                await self.reset_allowance_for_teacher(
                    teacher=teacher,
                    base_amount=default_allowance,
                    admin_id=admin_id
                )
                teacher_count += 1
            
            program_count += 1
        
        audit_log.info(
            "admin.allowance.program_reset",
            actor_id=admin_id,
            actor_role="admin" if admin_id != "system" else "system",
            target_type="program",
            target_id=program_id or "all",
            details={
                "programs_processed": program_count,
                "students_reset": student_count,
                "teachers_reset": teacher_count,
                "date": str(today)
            }
        )
        
        return {
            "programs_processed": program_count,
            "students_reset": student_count,
            "teachers_reset": teacher_count,
            "date": str(today)
        }

    async def get_teacher_by_id(self, teacher_id: str) -> Optional[Teacher]:
        """Get a teacher by ID."""
        result = await self.pg.execute(
            select(Teacher).where(Teacher.teacher_id == UUID(teacher_id))
        )
        return result.scalar_one_or_none()

    async def get_all_active_teachers(self) -> List[Teacher]:
        """Get all active teachers."""
        result = await self.pg.execute(
            select(Teacher).where(Teacher.is_active == True)
        )
        return result.scalars().all()

    async def reset_single_teacher_allowance(
        self,
        admin_id: str,
        teacher_id: str,
        base_amount: Optional[Decimal] = None
    ) -> tuple[bool, str]:
        """
        Reset allowance for a single teacher.
        Returns (success, message).
        """
        teacher = await self.get_teacher_by_id(teacher_id)
        if not teacher:
            return False, "Teacher not found"
        
        if not teacher.is_active:
            return False, "Teacher is inactive"
        
        await self.reset_allowance_for_teacher(
            teacher=teacher,
            base_amount=base_amount,
            admin_id=admin_id
        )
        
        audit_log.log_allowance_reset(
            admin_id=admin_id,
            target_id=teacher_id,
            scope="single_teacher"
        )
        
        return True, "Teacher allowance reset successfully"

    async def bump_teacher_allowance(
        self,
        admin_id: str,
        teacher_id: str,
        bonus_amount: Decimal
    ) -> tuple[bool, str, Optional[Decimal]]:
        """
        Add bonus to a teacher's daily allowance.
        Returns (success, message, new_total).
        """
        teacher = await self.get_teacher_by_id(teacher_id)
        if not teacher:
            return False, "Teacher not found", None
        
        if not teacher.is_active:
            return False, "Teacher is inactive", None
        
        today = date.today()
        
        # Get today's allowance
        result = await self.pg.execute(
            select(TeacherDailyAllowance).where(
                TeacherDailyAllowance.teacher_id == teacher.teacher_id,
                TeacherDailyAllowance.date == today
            )
        )
        allowance = result.scalar_one_or_none()
        
        if not allowance:
            # Create allowance first
            allowance = await self.reset_allowance_for_teacher(teacher, admin_id=admin_id)
        
        # Add bonus
        allowance.bonus_amount += bonus_amount
        allowance.total_amount = allowance.base_amount + allowance.bonus_amount
        
        await self.pg.flush()
        
        # Update Redis cache
        await self.redis.set_store_token(
            student_id=f"teacher_{teacher.teacher_id}",
            date=str(today),
            balance=allowance.total_amount
        )
        
        audit_log.info(
            "admin.allowance.teacher_bump",
            actor_id=admin_id,
            actor_role="admin",
            target_type="teacher",
            target_id=teacher_id,
            details={"bonus_amount": bonus_amount, "new_total": allowance.total_amount}
        )
        
        return True, "Teacher bonus added successfully", allowance.total_amount
