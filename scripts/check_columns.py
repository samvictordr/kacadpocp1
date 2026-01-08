#!/usr/bin/env python3
"""Check programs table columns."""

import asyncio
import asyncpg

POSTGRES_URI = "postgresql://postgreskau_user:NFb34JmL6SHYVUyCgVE2ro97MvWR2KLM@dpg-d5dd5du3jp1c73eprgp0-a.frankfurt-postgres.render.com/postgreskau"

async def check_columns():
    conn = await asyncpg.connect(POSTGRES_URI)
    
    columns = await conn.fetch("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'programs'
        ORDER BY ordinal_position
    """)
    
    print("Programs table columns:")
    for col in columns:
        print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
    
    await conn.close()

asyncio.run(check_columns())
