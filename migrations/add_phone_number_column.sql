-- Migration: Add phone_number column to students table
-- Date: 2026-01-06
-- Description: Replace national_id with phone_number field

-- Add phone_number column to students table
ALTER TABLE students ADD COLUMN IF NOT EXISTS phone_number TEXT;

-- Add comment
COMMENT ON COLUMN students.phone_number IS 'Student phone number for contact purposes';
