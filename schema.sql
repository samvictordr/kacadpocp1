-- ============================================================
-- Academy Program Database Schema
-- Phase 1: Attendance + Allowance System
-- PostgreSQL Schema Definition
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Programs Table
-- Represents academic programs/courses of study
-- ============================================================
CREATE TABLE programs (
    program_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    cost_center_code TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_programs_active ON programs(active);

-- ============================================================
-- Students Table
-- Links to MongoDB user via user_id
-- ============================================================
CREATE TABLE students (
    student_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone_number TEXT,
    program_id UUID NOT NULL REFERENCES programs(program_id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_students_user_id ON students(user_id);
CREATE INDEX idx_students_program_id ON students(program_id);
CREATE INDEX idx_students_active ON students(is_active);

-- ============================================================
-- Daily Allowances Table
-- Tracks daily allowance allocations per student
-- ============================================================
CREATE TABLE daily_allowances (
    allowance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(student_id),
    date DATE NOT NULL,
    base_amount DECIMAL(10, 2) NOT NULL,
    bonus_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(10, 2) NOT NULL,
    reset_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_student_date UNIQUE (student_id, date)
);

CREATE INDEX idx_daily_allowances_student_id ON daily_allowances(student_id);
CREATE INDEX idx_daily_allowances_date ON daily_allowances(date);
CREATE INDEX idx_daily_allowances_student_date ON daily_allowances(student_id, date);

-- ============================================================
-- Store Transactions Table
-- Records all store purchases
-- ============================================================
CREATE TABLE store_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES students(student_id),
    program_id UUID NOT NULL REFERENCES programs(program_id),
    amount DECIMAL(10, 2) NOT NULL,
    balance_after DECIMAL(10, 2) NOT NULL,
    scanned_by TEXT NOT NULL,
    location TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_store_transactions_student_id ON store_transactions(student_id);
CREATE INDEX idx_store_transactions_created_at ON store_transactions(created_at);
CREATE INDEX idx_store_transactions_scanned_by ON store_transactions(scanned_by);

-- ============================================================
-- Classes Table
-- Represents class sections taught by teachers
-- ============================================================
CREATE TABLE classes (
    class_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    program_id UUID NOT NULL REFERENCES programs(program_id),
    teacher_id UUID NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_classes_program_id ON classes(program_id);
CREATE INDEX idx_classes_teacher_id ON classes(teacher_id);
CREATE INDEX idx_classes_active ON classes(active);

-- ============================================================
-- Class Enrollments Table
-- Many-to-many relationship between classes and students
-- ============================================================
CREATE TABLE class_enrollments (
    class_id UUID NOT NULL REFERENCES classes(class_id),
    student_id UUID NOT NULL REFERENCES students(student_id),
    PRIMARY KEY (class_id, student_id)
);

CREATE INDEX idx_class_enrollments_student_id ON class_enrollments(student_id);

-- ============================================================
-- Attendance Sessions Table
-- Represents a single attendance-taking session
-- ============================================================
CREATE TYPE attendance_mode AS ENUM ('static', 'dynamic');

CREATE TABLE attendance_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID NOT NULL REFERENCES classes(class_id),
    date DATE NOT NULL,
    mode attendance_mode NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE INDEX idx_attendance_sessions_class_id ON attendance_sessions(class_id);
CREATE INDEX idx_attendance_sessions_date ON attendance_sessions(date);
CREATE INDEX idx_attendance_sessions_class_date ON attendance_sessions(class_id, date);

-- ============================================================
-- Attendance Records Table
-- Individual attendance entries for students in a session
-- ============================================================
CREATE TYPE attendance_status AS ENUM ('present', 'absent');

CREATE TABLE attendance_records (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES attendance_sessions(session_id),
    student_id UUID NOT NULL REFERENCES students(student_id),
    status attendance_status NOT NULL,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_session_student UNIQUE (session_id, student_id)
);

CREATE INDEX idx_attendance_records_session_id ON attendance_records(session_id);
CREATE INDEX idx_attendance_records_student_id ON attendance_records(student_id);

-- ============================================================
-- Sample Data for Testing (Optional)
-- ============================================================

-- Insert sample program
INSERT INTO programs (program_id, name, cost_center_code, active) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Computer Science', 'CS-001', TRUE),
    ('22222222-2222-2222-2222-222222222222', 'Business Administration', 'BA-001', TRUE);

-- Note: Students and other data should be created via the API
-- after creating corresponding MongoDB user records.
