-- Migration: Add program duration columns
-- Description: Adds start_date and end_date columns to programs table for program duration tracking
-- Date: 2026-01-07

-- Add start_date column to programs table
ALTER TABLE programs 
ADD COLUMN IF NOT EXISTS start_date DATE;

-- Add end_date column to programs table  
ALTER TABLE programs 
ADD COLUMN IF NOT EXISTS end_date DATE;

-- Create index on end_date for efficient expired program queries
CREATE INDEX IF NOT EXISTS idx_programs_end_date ON programs(end_date);

-- Comment on columns
COMMENT ON COLUMN programs.start_date IS 'Program start date';
COMMENT ON COLUMN programs.end_date IS 'Program end date - auto-deactivate when passed';
