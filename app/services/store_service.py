"""
Store service.
Handles store QR validation, balance checking, and transactions.
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.postgres_models import Student, Program, StoreTransaction, DailyAllowance
from app.db.redis import RedisClient
from app.core.config import settings
from app.core.logging import audit_log


class StoreService:
    """Service for store operations."""
    
    def __init__(
        self,
        pg_session: AsyncSession,
        mongo_db: AsyncIOMotorDatabase,
        redis: RedisClient
    ):
        self.pg = pg_session
        self.mongo = mongo_db
        self.redis = redis
    
    async def get_student_by_id(self, student_id: str) -> Optional[Student]:
        """Get student by student_id."""
        result = await self.pg.execute(
            select(Student).where(Student.student_id == UUID(student_id))
        )
        return result.scalar_one_or_none()
    
    async def get_student_by_user_id(self, user_id: str) -> Optional[Student]:
        """Get student by user_id."""
        result = await self.pg.execute(
            select(Student).where(Student.user_id == UUID(user_id))
        )
        return result.scalar_one_or_none()
    
    async def get_today_allowance(self, student_id: UUID) -> Optional[DailyAllowance]:
        """Get today's allowance for a student."""
        today = date.today()
        result = await self.pg.execute(
            select(DailyAllowance).where(
                DailyAllowance.student_id == student_id,
                DailyAllowance.date == today
            )
        )
        return result.scalar_one_or_none()
    
    async def get_today_spent(self, student_id: UUID) -> Decimal:
        """Get total amount spent today by a student."""
        today = date.today()
        result = await self.pg.execute(
            select(func.coalesce(func.sum(StoreTransaction.amount), Decimal("0.00")))
            .where(
                StoreTransaction.student_id == student_id,
                func.date(StoreTransaction.created_at) == today
            )
        )
        return result.scalar()
    
    async def get_balance(self, student_id: UUID) -> Optional[dict]:
        """Get current balance for a student."""
        allowance = await self.get_today_allowance(student_id)
        if not allowance:
            return None
        
        spent = await self.get_today_spent(student_id)
        remaining = allowance.total_amount - spent
        
        return {
            "student_id": str(student_id),
            "date": str(allowance.date),
            "base_amount": allowance.base_amount,
            "bonus_amount": allowance.bonus_amount,
            "total_amount": allowance.total_amount,
            "spent_today": spent,
            "remaining": max(Decimal("0.00"), remaining)
        }
    
    async def generate_store_qr(self, user_id: str) -> Optional[dict]:
        """
        Get store QR data for a student.
        Caches balance in Redis for fast access.
        """
        student = await self.get_student_by_user_id(user_id)
        if not student:
            return None
        
        balance_info = await self.get_balance(student.student_id)
        if not balance_info:
            return None
        
        today = str(date.today())
        
        # Cache in Redis for fast store scanning
        await self.redis.set_store_token(
            student_id=str(student.student_id),
            date=today,
            balance=balance_info["remaining"]
        )
        
        return {
            "student_id": str(student.student_id),
            "date": today,
            "balance": balance_info["remaining"]
        }
    
    async def scan_student(self, student_id: str, staff_user_id: str) -> tuple[bool, str, Optional[dict]]:
        """
        Scan a student's QR to check their balance.
        Returns (success, message, data).
        """
        student = await self.get_student_by_id(student_id)
        if not student:
            return False, "Student not found", None
        
        if not student.is_active:
            return False, "Student account is inactive", None
        
        # Get program info
        result = await self.pg.execute(
            select(Program).where(Program.program_id == student.program_id)
        )
        program = result.scalar_one_or_none()
        
        balance_info = await self.get_balance(student.student_id)
        if not balance_info:
            return False, "No allowance set for today", None
        
        return True, "Student found", {
            "student_id": str(student.student_id),
            "student_name": student.full_name,
            "program_name": program.name if program else "Unknown",
            "balance": balance_info["remaining"],
            "date": str(date.today())
        }
    
    async def charge_student(
        self,
        staff_user_id: str,
        student_id: str,
        amount: Decimal,
        location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> tuple[bool, str, Optional[dict]]:
        """
        Charge a student's allowance.
        Returns (success, message, transaction_data).
        """
        student = await self.get_student_by_id(student_id)
        if not student:
            return False, "Student not found", None
        
        if not student.is_active:
            return False, "Student account is inactive", None
        
        balance_info = await self.get_balance(student.student_id)
        if not balance_info:
            return False, "No allowance set for today", None
        
        current_balance = balance_info["remaining"]
        
        if amount > current_balance:
            return False, f"Insufficient balance. Available: {current_balance:.2f}", None
        
        # Calculate new balance
        new_balance = current_balance - amount
        
        # Create transaction
        transaction = StoreTransaction(
            student_id=student.student_id,
            program_id=student.program_id,
            amount=amount,
            balance_after=new_balance,
            scanned_by=staff_user_id,  # Store as text per spec
            location=location,
            notes=notes
        )
        
        self.pg.add(transaction)
        await self.pg.flush()
        
        # Update Redis cache
        today = str(date.today())
        await self.redis.update_store_balance(
            student_id=student_id,
            date=today,
            new_balance=new_balance
        )
        
        audit_log.log_store_transaction(
            staff_id=staff_user_id,
            student_id=student_id,
            amount=amount,
            balance_after=new_balance,
            location=location
        )
        
        return True, "Transaction successful", {
            "success": True,
            "transaction_id": str(transaction.transaction_id),
            "student_id": student_id,
            "amount": amount,
            "balance_after": new_balance,
            "message": f"Charged {amount:.2f}. Remaining balance: {new_balance:.2f}"
        }
