#!/usr/bin/env python3
"""Migration to add scanned_by column to attendance_records table."""

import asyncio

POSTGRES_URL = "postgresql+asyncpg://postgreskau_user:NFb34JmL6SHYVUyCgVE2ro97MvWR2KLM@dpg-d5dd5du3jp1c73eprgp0-a.frankfurt-postgres.render.com/postgreskau?ssl=require"


async def run_migration():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    
    print("=" * 60)
    print("MIGRATION: Add scanned_by to attendance_records")
    print("=" * 60)
    
    engine = create_async_engine(POSTGRES_URL, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_factory() as session:
        # Check if column exists
        result = await session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'attendance_records' AND column_name = 'scanned_by'
        """))
        exists = result.fetchone()
        
        if exists:
            print("✅ Column 'scanned_by' already exists")
        else:
            print("➕ Adding 'scanned_by' column...")
            await session.execute(text("""
                ALTER TABLE attendance_records 
                ADD COLUMN scanned_by UUID
            """))
            await session.commit()
            print("✅ Column 'scanned_by' added successfully")
        
        # Verify table structure
        result = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'attendance_records'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        print("\n📋 Current attendance_records columns:")
        for col in columns:
            print(f"   - {col[0]} ({col[1]})")
    
    await engine.dispose()
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    asyncio.run(run_migration())
