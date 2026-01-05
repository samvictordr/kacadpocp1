"""
Dashboard API Endpoints
Provides all data endpoints for the admin dashboard
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import datetime, timedelta
import uuid
import hashlib
import io
import csv

from app.db.postgres import get_postgres_pool
from app.db.mongodb import get_mongo_db
from app.db.redis import get_redis_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ==================== HEALTH & TELEMETRY ====================

@router.get("/api/health")
async def get_health_status():
    """Get health status of all services."""
    result = {
        "postgres": {"status": "unknown", "connected": False},
        "mongodb": {"status": "unknown", "connected": False},
        "redis": {"status": "unknown", "connected": False},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            result["postgres"] = {"status": "healthy", "connected": True}
    except Exception as e:
        result["postgres"] = {"status": "unhealthy", "connected": False, "error": str(e)}
    
    try:
        db = await get_mongo_db()
        await db.command("ping")
        result["mongodb"] = {"status": "healthy", "connected": True}
    except Exception as e:
        result["mongodb"] = {"status": "unhealthy", "connected": False, "error": str(e)}
    
    try:
        redis = await get_redis_client()
        if redis:
            await redis.ping()
            result["redis"] = {"status": "healthy", "connected": True}
    except Exception as e:
        result["redis"] = {"status": "unhealthy", "connected": False, "error": str(e)}
    
    all_healthy = all([
        result["postgres"]["connected"],
        result["mongodb"]["connected"],
        result["redis"]["connected"]
    ])
    result["overall"] = "healthy" if all_healthy else "degraded"
    
    return result


@router.get("/api/stats")
async def get_dashboard_stats():
    """Get dashboard statistics."""
    stats = {
        "total_students": 0,
        "total_teachers": 0,
        "total_programs": 0,
        "transactions_today": 0,
        "revenue_today": 0,
        "attendance_today": 0,
        "active_qr_tokens": 0,
        "active_sessions": 0
    }
    
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            stats["total_students"] = await conn.fetchval(
                "SELECT COUNT(*) FROM students WHERE is_active = true"
            ) or 0
            stats["total_teachers"] = await conn.fetchval(
                "SELECT COUNT(*) FROM teachers WHERE is_active = true"
            ) or 0
            stats["total_programs"] = await conn.fetchval(
                "SELECT COUNT(*) FROM programs WHERE is_active = true"
            ) or 0
            stats["transactions_today"] = await conn.fetchval("""
                SELECT COUNT(*) FROM store_transactions 
                WHERE DATE(transaction_time) = CURRENT_DATE
            """) or 0
            stats["revenue_today"] = float(await conn.fetchval("""
                SELECT COALESCE(SUM(total_amount), 0) FROM store_transactions 
                WHERE DATE(transaction_time) = CURRENT_DATE
            """) or 0)
            stats["attendance_today"] = await conn.fetchval("""
                SELECT COUNT(*) FROM attendance_records 
                WHERE DATE(check_in_time) = CURRENT_DATE
            """) or 0
    except:
        pass
    
    try:
        redis = await get_redis_client()
        if redis:
            qr_keys = await redis.keys("qr:*")
            stats["active_qr_tokens"] = len(qr_keys) if qr_keys else 0
            session_keys = await redis.keys("session:*")
            stats["active_sessions"] = len(session_keys) if session_keys else 0
    except:
        pass
    
    return stats


@router.get("/api/telemetry")
async def get_telemetry():
    """Get key telemetry metrics."""
    metrics = {
        "postgres": {"database_size": "N/A", "table_counts": {}},
        "mongodb": {"total_documents": 0, "collections": {}},
        "redis": {"memory": "N/A", "keys": 0},
        "transactions": {"today": 0, "week": 0, "month": 0},
        "attendance": {"today": 0, "week": 0}
    }
    
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
            metrics["postgres"]["database_size"] = size
            
            tables = await conn.fetch("""
                SELECT relname as table_name, n_live_tup as row_count
                FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 10
            """)
            metrics["postgres"]["table_counts"] = {t["table_name"]: t["row_count"] for t in tables}
            
            metrics["transactions"]["today"] = await conn.fetchval("""
                SELECT COUNT(*) FROM store_transactions WHERE DATE(transaction_time) = CURRENT_DATE
            """) or 0
            metrics["transactions"]["week"] = await conn.fetchval("""
                SELECT COUNT(*) FROM store_transactions WHERE transaction_time >= CURRENT_DATE - INTERVAL '7 days'
            """) or 0
            metrics["transactions"]["month"] = await conn.fetchval("""
                SELECT COUNT(*) FROM store_transactions WHERE transaction_time >= CURRENT_DATE - INTERVAL '30 days'
            """) or 0
            metrics["attendance"]["today"] = await conn.fetchval("""
                SELECT COUNT(*) FROM attendance_records WHERE DATE(check_in_time) = CURRENT_DATE
            """) or 0
            metrics["attendance"]["week"] = await conn.fetchval("""
                SELECT COUNT(*) FROM attendance_records WHERE check_in_time >= CURRENT_DATE - INTERVAL '7 days'
            """) or 0
    except:
        pass
    
    try:
        db = await get_mongo_db()
        collections = await db.list_collection_names()
        for coll_name in collections:
            count = await db[coll_name].count_documents({})
            metrics["mongodb"]["collections"][coll_name] = count
            metrics["mongodb"]["total_documents"] += count
    except:
        pass
    
    try:
        redis = await get_redis_client()
        if redis:
            info = await redis.info()
            metrics["redis"]["memory"] = info.get("used_memory_human", "N/A")
            metrics["redis"]["keys"] = await redis.dbsize()
    except:
        pass
    
    return metrics


@router.get("/api/trends/transactions")
async def get_transaction_trends():
    """Get 7-day transaction trends."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DATE(transaction_time) as date, COUNT(*) as count,
                       COALESCE(SUM(total_amount), 0) as total
                FROM store_transactions
                WHERE transaction_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(transaction_time) ORDER BY date
            """)
            return [{"date": str(r["date"]), "count": r["count"], "total": float(r["total"])} for r in rows]
    except:
        return []


@router.get("/api/trends/attendance")
async def get_attendance_trends():
    """Get 7-day attendance trends."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DATE(check_in_time) as date, COUNT(*) as count
                FROM attendance_records
                WHERE check_in_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(check_in_time) ORDER BY date
            """)
            return [{"date": str(r["date"]), "count": r["count"]} for r in rows]
    except:
        return []


# ==================== USER MANAGEMENT ====================

@router.get("/api/users")
async def get_all_users(role: Optional[str] = None):
    """Get users from MongoDB."""
    try:
        db = await get_mongo_db()
        query = {"role": role} if role else {}
        cursor = db.users.find(query)
        users = await cursor.to_list(length=1000)
        for user in users:
            user["_id"] = str(user["_id"])
            user.pop("password_hash", None)
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/students")
async def get_all_students():
    """Get all students."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT s.student_id, s.user_id, s.full_name, s.national_id,
                       s.program_id, s.is_active, p.name as program_name
                FROM students s
                LEFT JOIN programs p ON s.program_id = p.program_id
                ORDER BY s.full_name
            """)
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/teachers")
async def get_all_teachers():
    """Get all teachers."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT t.teacher_id, t.user_id, t.full_name, t.employee_id,
                       t.program_id, t.is_active, p.name as program_name
                FROM teachers t
                LEFT JOIN programs p ON t.program_id = p.program_id
                ORDER BY t.full_name
            """)
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/programs")
async def get_all_programs():
    """Get all programs."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT p.program_id, p.name, p.cost_center, 
                       p.default_daily_allowance, p.is_active,
                       COUNT(DISTINCT s.student_id) as student_count,
                       COUNT(DISTINCT t.teacher_id) as teacher_count
                FROM programs p
                LEFT JOIN students s ON p.program_id = s.program_id AND s.is_active = true
                LEFT JOIN teachers t ON p.program_id = t.program_id AND t.is_active = true
                GROUP BY p.program_id ORDER BY p.name
            """)
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users")
async def create_user(data: dict):
    """Create a new user."""
    try:
        db = await get_mongo_db()
        pool = await get_postgres_pool()
        
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(data.get("password", "temp123").encode()).hexdigest()
        
        await db.users.insert_one({
            "_id": user_id,
            "email": data["email"],
            "full_name": data["full_name"],
            "password_hash": password_hash,
            "role": data["role"],
            "is_active": True,
            "created_at": datetime.utcnow()
        })
        
        async with pool.acquire() as conn:
            if data["role"] == "student":
                await conn.execute("""
                    INSERT INTO students (student_id, user_id, full_name, national_id, program_id, is_active)
                    VALUES ($1, $2, $3, $4, $5, true)
                """, str(uuid.uuid4()), user_id, data["full_name"], 
                    data.get("national_id", ""), data.get("program_id"))
            elif data["role"] == "teacher":
                await conn.execute("""
                    INSERT INTO teachers (teacher_id, user_id, full_name, employee_id, program_id, is_active)
                    VALUES ($1, $2, $3, $4, $5, true)
                """, str(uuid.uuid4()), user_id, data["full_name"],
                    data.get("employee_id", ""), data.get("program_id"))
        
        return {"success": True, "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/users/{user_id}/status")
async def update_user_status(user_id: str, data: dict):
    """Update user status."""
    try:
        db = await get_mongo_db()
        pool = await get_postgres_pool()
        is_active = data.get("is_active", True)
        
        await db.users.update_one({"_id": user_id}, {"$set": {"is_active": is_active}})
        
        async with pool.acquire() as conn:
            await conn.execute("UPDATE students SET is_active = $1 WHERE user_id = $2", is_active, user_id)
            await conn.execute("UPDATE teachers SET is_active = $1 WHERE user_id = $2", is_active, user_id)
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/users/{user_id}")
async def delete_user(user_id: str):
    """Delete a user."""
    try:
        db = await get_mongo_db()
        pool = await get_postgres_pool()
        
        await db.users.delete_one({"_id": user_id})
        
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM students WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM teachers WHERE user_id = $1", user_id)
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PROGRAMS ====================

@router.post("/api/programs")
async def create_program(data: dict):
    """Create a program."""
    try:
        pool = await get_postgres_pool()
        program_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO programs (program_id, name, cost_center, default_daily_allowance, is_active)
                VALUES ($1, $2, $3, $4, true)
            """, program_id, data["name"], data["cost_center"], 
                float(data.get("default_daily_allowance", 50.0)))
        
        return {"success": True, "program_id": program_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/programs/{program_id}")
async def update_program(program_id: str, data: dict):
    """Update a program."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE programs SET name = $1, cost_center = $2, 
                default_daily_allowance = $3, is_active = $4 WHERE program_id = $5
            """, data["name"], data["cost_center"], 
                float(data.get("default_daily_allowance", 50.0)),
                data.get("is_active", True), program_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/programs/{program_id}")
async def delete_program(program_id: str):
    """Delete a program."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM students WHERE program_id = $1", program_id
            ) or 0
            if count > 0:
                raise HTTPException(status_code=400, detail="Program has assigned students")
            await conn.execute("DELETE FROM programs WHERE program_id = $1", program_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ALLOWANCES ====================

@router.get("/api/allowances")
async def get_allowances(filter_date: Optional[str] = None):
    """Get allowances."""
    try:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            if filter_date:
                rows = await conn.fetch("""
                    SELECT da.*, s.full_name FROM daily_allowances da
                    JOIN students s ON da.student_id = s.student_id
                    WHERE da.date = $1 ORDER BY s.full_name
                """, filter_date)
            else:
                rows = await conn.fetch("""
                    SELECT da.*, s.full_name FROM daily_allowances da
                    JOIN students s ON da.student_id = s.student_id
                    ORDER BY da.date DESC, s.full_name LIMIT 100
                """)
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/allowances")
async def set_allowance(data: dict):
    """Set allowance."""
    try:
        pool = await get_postgres_pool()
        base = float(data["base_amount"])
        bonus = float(data.get("bonus_amount", 0))
        
        async with pool.acquire() as conn:
            existing = await conn.fetchval("""
                SELECT allowance_id FROM daily_allowances 
                WHERE student_id = $1 AND date = $2
            """, data["student_id"], data["date"])
            
            if existing:
                await conn.execute("""
                    UPDATE daily_allowances SET base_amount=$1, bonus_amount=$2, total_amount=$3
                    WHERE student_id=$4 AND date=$5
                """, base, bonus, base+bonus, data["student_id"], data["date"])
            else:
                await conn.execute("""
                    INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, str(uuid.uuid4()), data["student_id"], data["date"], base, bonus, base+bonus)
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/allowances/bulk")
async def bulk_allowances(data: dict):
    """Set allowances for all students in a program."""
    try:
        pool = await get_postgres_pool()
        base = float(data["base_amount"])
        bonus = float(data.get("bonus_amount", 0))
        count = 0
        
        async with pool.acquire() as conn:
            students = await conn.fetch(
                "SELECT student_id FROM students WHERE program_id = $1 AND is_active = true",
                data["program_id"]
            )
            for s in students:
                existing = await conn.fetchval("""
                    SELECT allowance_id FROM daily_allowances 
                    WHERE student_id = $1 AND date = $2
                """, s["student_id"], data["date"])
                
                if existing:
                    await conn.execute("""
                        UPDATE daily_allowances SET base_amount=$1, bonus_amount=$2, total_amount=$3
                        WHERE student_id=$4 AND date=$5
                    """, base, bonus, base+bonus, s["student_id"], data["date"])
                else:
                    await conn.execute("""
                        INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, str(uuid.uuid4()), s["student_id"], data["date"], base, bonus, base+bonus)
                count += 1
        
        return {"success": True, "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== BULK UPLOAD ====================

@router.post("/api/bulk/students")
async def bulk_upload_students(file: UploadFile = File(...), program_id: str = Form(...)):
    """Bulk upload students from CSV."""
    try:
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        db = await get_mongo_db()
        pool = await get_postgres_pool()
        created, errors = 0, []
        
        for row in reader:
            try:
                user_id = str(uuid.uuid4())
                password_hash = hashlib.sha256("temp123".encode()).hexdigest()
                
                await db.users.insert_one({
                    "_id": user_id, "email": row["email"], "full_name": row["full_name"],
                    "password_hash": password_hash, "role": "student",
                    "is_active": True, "created_at": datetime.utcnow()
                })
                
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO students (student_id, user_id, full_name, national_id, program_id, is_active)
                        VALUES ($1, $2, $3, $4, $5, true)
                    """, str(uuid.uuid4()), user_id, row["full_name"], row.get("national_id", ""), program_id)
                created += 1
            except Exception as e:
                errors.append({"row": row.get("email", "?"), "error": str(e)})
        
        return {"success": True, "created": created, "errors": errors}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/bulk/teachers")
async def bulk_upload_teachers(file: UploadFile = File(...), program_id: str = Form(...)):
    """Bulk upload teachers from CSV."""
    try:
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        db = await get_mongo_db()
        pool = await get_postgres_pool()
        created, errors = 0, []
        
        for row in reader:
            try:
                user_id = str(uuid.uuid4())
                password_hash = hashlib.sha256("temp123".encode()).hexdigest()
                
                await db.users.insert_one({
                    "_id": user_id, "email": row["email"], "full_name": row["full_name"],
                    "password_hash": password_hash, "role": "teacher",
                    "is_active": True, "created_at": datetime.utcnow()
                })
                
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO teachers (teacher_id, user_id, full_name, employee_id, program_id, is_active)
                        VALUES ($1, $2, $3, $4, $5, true)
                    """, str(uuid.uuid4()), user_id, row["full_name"], row.get("employee_id", ""), program_id)
                created += 1
            except Exception as e:
                errors.append({"row": row.get("email", "?"), "error": str(e)})
        
        return {"success": True, "created": created, "errors": errors}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AUTH ====================

@router.post("/api/auth/login")
async def admin_login(data: dict):
    """Admin login."""
    try:
        db = await get_mongo_db()
        password_hash = hashlib.sha256(data.get("password", "").encode()).hexdigest()
        
        user = await db.users.find_one({"email": data.get("email"), "role": "admin", "is_active": True})
        
        if not user or user.get("password_hash") != password_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = str(uuid.uuid4())
        redis = await get_redis_client()
        if redis:
            await redis.setex(f"admin_session:{token}", 86400, data.get("email"))
        
        return {"success": True, "token": token, "email": data.get("email"), "full_name": user.get("full_name", "Admin")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auth/verify")
async def verify_session(token: str):
    """Verify admin session."""
    try:
        redis = await get_redis_client()
        if redis:
            email = await redis.get(f"admin_session:{token}")
            if email:
                return {"valid": True, "email": email.decode() if isinstance(email, bytes) else email}
        return {"valid": False}
    except:
        return {"valid": False}
