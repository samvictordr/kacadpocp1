-- Migration: Add start_date and end_date to programs table
-- Date: 2026-01-07
-- Description: Add start and end date fields to programs to support program duration tracking

ALTER TABLE programs 
ADD COLUMN IF NOT EXISTS start_date DATE,
ADD COLUMN IF NOT EXISTS end_date DATE;

CREATE INDEX IF NOT EXISTS idx_programs_end_date ON programs(end_date) WHERE end_date IS NOT NULL AND is_active = true;

COMMENT ON COLUMN programs.start_date IS 'Start date of the program';
COMMENT ON COLUMN programs.end_date IS 'End date of the program - program will be auto-deactivated after this date';
