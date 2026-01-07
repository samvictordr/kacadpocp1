#!/usr/bin/env python3
"""
Migration script to add program duration columns to the database.
Run this script to add start_date and end_date columns to the programs table.
"""

import asyncio
import asyncpg
import sys

# Production database URI
POSTGRES_URI = "postgresql://postgreskau_user:NFb34JmL6SHYVUyCgVE2ro97MvWR2KLM@dpg-d5dd5du3jp1c73eprgp0-a.frankfurt-postgres.render.com/postgreskau"

MIGRATION_SQL = """
-- Add start_date column to programs table
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'programs' AND column_name = 'start_date') THEN
        ALTER TABLE programs ADD COLUMN start_date DATE;
        RAISE NOTICE 'Added start_date column';
    ELSE
        RAISE NOTICE 'start_date column already exists';
    END IF;
END $$;

-- Add end_date column to programs table
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'programs' AND column_name = 'end_date') THEN
        ALTER TABLE programs ADD COLUMN end_date DATE;
        RAISE NOTICE 'Added end_date column';
    ELSE
        RAISE NOTICE 'end_date column already exists';
    END IF;
END $$;

-- Create index on end_date for efficient expired program queries
CREATE INDEX IF NOT EXISTS idx_programs_end_date ON programs(end_date);
"""


async def run_migration():
    print("Connecting to PostgreSQL...")
    try:
        conn = await asyncpg.connect(POSTGRES_URI)
        print("Connected successfully!")
        
        print("\nRunning migration...")
        await conn.execute(MIGRATION_SQL)
        
        print("\nVerifying columns...")
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'programs' 
            AND column_name IN ('start_date', 'end_date')
            ORDER BY column_name
        """)
        
        for col in columns:
            print(f"  ✓ {col['column_name']}: {col['data_type']}")
        
        if len(columns) == 2:
            print("\n✅ Migration completed successfully!")
        else:
            print(f"\n⚠️ Warning: Expected 2 columns, found {len(columns)}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)
