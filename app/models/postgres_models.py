"""
SQLAlchemy ORM models for PostgreSQL tables.
These tables are the authoritative source of truth for attendance and transactions.
"""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, ForeignKey, 
    UniqueConstraint, Enum as SQLEnum, Text, Numeric
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import enum

from app.db.postgres import Base


class AttendanceMode(str, enum.Enum):
    """Mode of attendance session."""
    STATIC = "static"
    DYNAMIC = "dynamic"
    
    def __str__(self) -> str:
        return self.value


class AttendanceStatus(str, enum.Enum):
    """Status of attendance record."""
    PRESENT = "present"
    ABSENT = "absent"
    
    def __str__(self) -> str:
        return self.value


class Program(Base):
    """Program/course of study."""
    __tablename__ = "programs"
    
    program_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    cost_center_code = Column(Text, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    students = relationship("Student", back_populates="program")
    classes = relationship("Class", back_populates="program")


class Teacher(Base):
    """Teacher record linked to MongoDB user for meal allowance."""
    __tablename__ = "teachers"
    
    teacher_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), unique=True, nullable=False)
    full_name = Column(Text, nullable=False)
    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.program_id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    program = relationship("Program")
    daily_allowances = relationship("TeacherDailyAllowance", back_populates="teacher")
    meal_transactions = relationship("TeacherMealTransaction", back_populates="teacher")


class Student(Base):
    """Student record linked to MongoDB user."""
    __tablename__ = "students"
    
    student_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), unique=True, nullable=False)
    full_name = Column(Text, nullable=False)
    phone_number = Column(Text, unique=True, nullable=True)  # Saudi format: +966XXXXXXXXX
    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.program_id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    program = relationship("Program", back_populates="students")
    daily_allowances = relationship("DailyAllowance", back_populates="student")
    store_transactions = relationship("StoreTransaction", back_populates="student")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    class_enrollments = relationship("ClassEnrollment", back_populates="student")


class DailyAllowance(Base):
    """Daily allowance for a student."""
    __tablename__ = "daily_allowances"
    
    allowance_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(PGUUID(as_uuid=True), ForeignKey("students.student_id"), nullable=False)
    date = Column(Date, nullable=False)
    base_amount = Column(Numeric(10, 2), nullable=False)
    bonus_amount = Column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    reset_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('student_id', 'date', name='uq_student_date'),
    )
    
    # Relationships
    student = relationship("Student", back_populates="daily_allowances")


class StoreTransaction(Base):
    """Store purchase transaction."""
    __tablename__ = "store_transactions"
    
    transaction_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(PGUUID(as_uuid=True), ForeignKey("students.student_id"), nullable=False)
    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.program_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=False)
    scanned_by = Column(Text, nullable=False)  # Store staff user_id as text
    location = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    student = relationship("Student", back_populates="store_transactions")
    program = relationship("Program")


class Class(Base):
    """Class/section taught by a teacher."""
    __tablename__ = "classes"
    
    class_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.program_id"), nullable=False)
    teacher_id = Column(PGUUID(as_uuid=True), nullable=False)  # User ID from MongoDB
    active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    program = relationship("Program", back_populates="classes")
    enrollments = relationship("ClassEnrollment", back_populates="class_")
    attendance_sessions = relationship("AttendanceSession", back_populates="class_")


class ClassEnrollment(Base):
    """Student enrollment in a class."""
    __tablename__ = "class_enrollments"
    
    class_id = Column(PGUUID(as_uuid=True), ForeignKey("classes.class_id"), primary_key=True)
    student_id = Column(PGUUID(as_uuid=True), ForeignKey("students.student_id"), primary_key=True)
    
    # Relationships
    class_ = relationship("Class", back_populates="enrollments")
    student = relationship("Student", back_populates="class_enrollments")


class AttendanceSession(Base):
    """Attendance session created by teacher."""
    __tablename__ = "attendance_sessions"
    
    session_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(PGUUID(as_uuid=True), ForeignKey("classes.class_id"), nullable=False)
    date = Column(Date, nullable=False)
    mode = Column(
        SQLEnum(AttendanceMode, name='attendance_mode', create_type=False,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    created_by = Column(PGUUID(as_uuid=True), nullable=False)  # Teacher user_id
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    class_ = relationship("Class", back_populates="attendance_sessions")
    records = relationship("AttendanceRecord", back_populates="session")


class AttendanceRecord(Base):
    """Individual attendance record for a student in a session."""
    __tablename__ = "attendance_records"
    
    record_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(PGUUID(as_uuid=True), ForeignKey("attendance_sessions.session_id"), nullable=False)
    student_id = Column(PGUUID(as_uuid=True), ForeignKey("students.student_id"), nullable=False)
    status = Column(
        SQLEnum(AttendanceStatus, name='attendance_status', create_type=False,
                values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    scanned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('session_id', 'student_id', name='uq_session_student'),
    )
    
    # Relationships
    session = relationship("AttendanceSession", back_populates="records")
    student = relationship("Student", back_populates="attendance_records")


class TeacherDailyAllowance(Base):
    """Daily meal allowance for a teacher."""
    __tablename__ = "teacher_daily_allowances"
    
    allowance_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(PGUUID(as_uuid=True), ForeignKey("teachers.teacher_id"), nullable=False)
    date = Column(Date, nullable=False)
    base_amount = Column(Numeric(10, 2), nullable=False)
    bonus_amount = Column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    reset_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('teacher_id', 'date', name='uq_teacher_date'),
    )
    
    # Relationships
    teacher = relationship("Teacher", back_populates="daily_allowances")


class TeacherMealTransaction(Base):
    """Teacher meal purchase transaction."""
    __tablename__ = "teacher_meal_transactions"
    
    transaction_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(PGUUID(as_uuid=True), ForeignKey("teachers.teacher_id"), nullable=False)
    program_id = Column(PGUUID(as_uuid=True), ForeignKey("programs.program_id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    balance_after = Column(Numeric(10, 2), nullable=False)
    scanned_by = Column(Text, nullable=False)
    location = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    teacher = relationship("Teacher", back_populates="meal_transactions")
    program = relationship("Program")
