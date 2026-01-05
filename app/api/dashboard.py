"""
Dashboard API Endpoints
Provides all data endpoints for the admin dashboard
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import text
import uuid
import hashlib
import io
import csv

from app.db.postgres import async_session_factory
from app.db.mongodb import mongodb
from app.db.redis import redis_client
from app.core.security import verify_password, hash_password

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
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            result["postgres"] = {"status": "healthy", "connected": True}
    except Exception as e:
        result["postgres"] = {"status": "unhealthy", "connected": False, "error": str(e)}
    
    try:
        if mongodb.db is not None:
            await mongodb.client.admin.command("ping")
            result["mongodb"] = {"status": "healthy", "connected": True}
    except Exception as e:
        result["mongodb"] = {"status": "unhealthy", "connected": False, "error": str(e)}
    
    try:
        if redis_client.client is not None:
            await redis_client.client.ping()
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
        async with async_session_factory() as session:
            result = await session.execute(text(
                "SELECT COUNT(*) FROM students WHERE is_active = true"
            ))
            stats["total_students"] = result.scalar() or 0
            
            result = await session.execute(text(
                "SELECT COUNT(*) FROM teachers WHERE is_active = true"
            ))
            stats["total_teachers"] = result.scalar() or 0
            
            result = await session.execute(text(
                "SELECT COUNT(*) FROM programs WHERE is_active = true"
            ))
            stats["total_programs"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM store_transactions 
                WHERE DATE(created_at) = CURRENT_DATE
            """))
            stats["transactions_today"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COALESCE(SUM(amount), 0) FROM store_transactions 
                WHERE DATE(created_at) = CURRENT_DATE
            """))
            stats["revenue_today"] = float(result.scalar() or 0)
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM attendance_records 
                WHERE DATE(check_in_time) = CURRENT_DATE
            """))
            stats["attendance_today"] = result.scalar() or 0
    except:
        pass
    
    try:
        if redis_client.client is not None:
            qr_keys = await redis_client.client.keys("qr:*")
            stats["active_qr_tokens"] = len(qr_keys) if qr_keys else 0
            session_keys = await redis_client.client.keys("session:*")
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
        async with async_session_factory() as session:
            result = await session.execute(text(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            ))
            metrics["postgres"]["database_size"] = result.scalar()
            
            result = await session.execute(text("""
                SELECT relname as table_name, n_live_tup as row_count
                FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 10
            """))
            rows = result.fetchall()
            metrics["postgres"]["table_counts"] = {r[0]: r[1] for r in rows}
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM store_transactions WHERE DATE(created_at) = CURRENT_DATE
            """))
            metrics["transactions"]["today"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM store_transactions WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """))
            metrics["transactions"]["week"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM store_transactions WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            """))
            metrics["transactions"]["month"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM attendance_records WHERE DATE(check_in_time) = CURRENT_DATE
            """))
            metrics["attendance"]["today"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM attendance_records WHERE check_in_time >= CURRENT_DATE - INTERVAL '7 days'
            """))
            metrics["attendance"]["week"] = result.scalar() or 0
    except:
        pass
    
    try:
        if mongodb.db is not None:
            collections = await mongodb.db.list_collection_names()
            for coll_name in collections:
                count = await mongodb.db[coll_name].count_documents({})
                metrics["mongodb"]["collections"][coll_name] = count
                metrics["mongodb"]["total_documents"] += count
    except:
        pass
    
    try:
        if redis_client.client is not None:
            info = await redis_client.client.info()
            metrics["redis"]["memory"] = info.get("used_memory_human", "N/A")
            metrics["redis"]["keys"] = await redis_client.client.dbsize()
    except:
        pass
    
    return metrics


@router.get("/api/trends/transactions")
async def get_transaction_trends():
    """Get 7-day transaction trends."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT DATE(created_at) as date, COUNT(*) as count,
                       COALESCE(SUM(amount), 0) as total
                FROM store_transactions
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(created_at) ORDER BY date
            """))
            rows = result.fetchall()
            return [{"date": str(r[0]), "count": r[1], "total": float(r[2])} for r in rows]
    except:
        return []


@router.get("/api/trends/attendance")
async def get_attendance_trends():
    """Get 7-day attendance trends."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT DATE(check_in_time) as date, COUNT(*) as count
                FROM attendance_records
                WHERE check_in_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(check_in_time) ORDER BY date
            """))
            rows = result.fetchall()
            return [{"date": str(r[0]), "count": r[1]} for r in rows]
    except:
        return []


# ==================== USER MANAGEMENT ====================

@router.get("/api/users")
async def get_all_users(role: Optional[str] = None):
    """Get users from MongoDB."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
        query = {"role": role} if role else {}
        cursor = mongodb.db.users.find(query)
        users = await cursor.to_list(length=1000)
        for user in users:
            user["_id"] = str(user["_id"])
            user.pop("password_hash", None)
        return users
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/students")
async def get_all_students():
    """Get all students."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT s.student_id, s.user_id, s.full_name, s.phone_number,
                       s.program_id, s.is_active, p.name as program_name
                FROM students s
                LEFT JOIN programs p ON s.program_id = p.program_id
                ORDER BY s.full_name
            """))
            rows = result.fetchall()
            columns = ["student_id", "user_id", "full_name", "phone_number", "program_id", "is_active", "program_name"]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/teachers")
async def get_all_teachers():
    """Get all teachers."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT t.teacher_id, t.user_id, t.full_name, t.employee_id,
                       t.program_id, t.is_active, p.name as program_name
                FROM teachers t
                LEFT JOIN programs p ON t.program_id = p.program_id
                ORDER BY t.full_name
            """))
            rows = result.fetchall()
            columns = ["teacher_id", "user_id", "full_name", "employee_id", "program_id", "is_active", "program_name"]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/programs")
async def get_all_programs():
    """Get all programs."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT p.program_id, p.name, p.cost_center_code, p.active,
                       COUNT(DISTINCT s.student_id) as student_count,
                       COUNT(DISTINCT t.teacher_id) as teacher_count
                FROM programs p
                LEFT JOIN students s ON p.program_id = s.program_id AND s.is_active = true
                LEFT JOIN teachers t ON p.program_id = t.program_id AND t.is_active = true
                GROUP BY p.program_id ORDER BY p.name
            """))
            rows = result.fetchall()
            columns = ["program_id", "name", "cost_center_code", "active", "student_count", "teacher_count"]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users")
async def create_user(data: dict):
    """Create a new user."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
            
        user_id = str(uuid.uuid4())
        password_hash = hash_password(data.get("password", "temp123"))
        
        await mongodb.db.users.insert_one({
            "_id": user_id,
            "user_id": user_id,
            "email": data["email"],
            "name": data["full_name"],
            "full_name": data["full_name"],
            "role": data["role"],
            "status": "active",
            "auth": {
                "password_hash": password_hash,
                "password_last_changed": datetime.utcnow()
            },
            "associations": {},
            "metadata": {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        })
        
        async with async_session_factory() as session:
            if data["role"] == "student":
                await session.execute(text("""
                    INSERT INTO students (student_id, user_id, full_name, phone_number, program_id, is_active)
                    VALUES (:student_id, :user_id, :full_name, :phone_number, :program_id, true)
                """), {
                    "student_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "full_name": data["full_name"],
                    "phone_number": data.get("phone_number", ""),
                    "program_id": data.get("program_id")
                })
            elif data["role"] == "teacher":
                await session.execute(text("""
                    INSERT INTO teachers (teacher_id, user_id, full_name, employee_id, program_id, is_active)
                    VALUES (:teacher_id, :user_id, :full_name, :employee_id, :program_id, true)
                """), {
                    "teacher_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "full_name": data["full_name"],
                    "employee_id": data.get("employee_id", ""),
                    "program_id": data.get("program_id")
                })
            await session.commit()
        
        return {"success": True, "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/users/{user_id}/status")
async def update_user_status(user_id: str, data: dict):
    """Update user status."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
            
        is_active = data.get("is_active", True)
        
        await mongodb.db.users.update_one({"user_id": user_id}, {"$set": {"is_active": is_active}})
        
        async with async_session_factory() as session:
            await session.execute(text(
                "UPDATE students SET is_active = :is_active WHERE user_id = :user_id"
            ), {"is_active": is_active, "user_id": user_id})
            await session.execute(text(
                "UPDATE teachers SET is_active = :is_active WHERE user_id = :user_id"
            ), {"is_active": is_active, "user_id": user_id})
            await session.commit()
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/users/{user_id}")
async def delete_user(user_id: str):
    """Delete a user."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
            
        await mongodb.db.users.delete_one({"user_id": user_id})
        
        async with async_session_factory() as session:
            await session.execute(text(
                "DELETE FROM students WHERE user_id = :user_id"
            ), {"user_id": user_id})
            await session.execute(text(
                "DELETE FROM teachers WHERE user_id = :user_id"
            ), {"user_id": user_id})
            await session.commit()
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PROGRAMS ====================

@router.post("/api/programs")
async def create_program(data: dict):
    """Create a program."""
    try:
        program_id = str(uuid.uuid4())
        
        async with async_session_factory() as session:
            await session.execute(text("""
                INSERT INTO programs (program_id, name, cost_center_code, active)
                VALUES (:program_id, :name, :cost_center_code, true)
            """), {
                "program_id": program_id,
                "name": data["name"],
                "cost_center_code": data.get("cost_center_code", "DEFAULT")
            })
            await session.commit()
        
        return {"success": True, "program_id": program_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/programs/{program_id}")
async def update_program(program_id: str, data: dict):
    """Update a program."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("""
                UPDATE programs SET name = :name, cost_center_code = :cost_center_code, 
                active = :active WHERE program_id = :program_id
            """), {
                "name": data["name"],
                "cost_center_code": data.get("cost_center_code", "DEFAULT"),
                "active": data.get("active", True),
                "program_id": program_id
            })
            await session.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/programs/{program_id}")
async def delete_program(program_id: str):
    """Delete a program."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text(
                "SELECT COUNT(*) FROM students WHERE program_id = :program_id"
            ), {"program_id": program_id})
            count = result.scalar() or 0
            
            if count > 0:
                raise HTTPException(status_code=400, detail="Program has assigned students")
            
            await session.execute(text(
                "DELETE FROM programs WHERE program_id = :program_id"
            ), {"program_id": program_id})
            await session.commit()
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
        async with async_session_factory() as session:
            if filter_date:
                result = await session.execute(text("""
                    SELECT da.allowance_id, da.student_id, da.date, da.base_amount, 
                           da.bonus_amount, da.total_amount, s.full_name 
                    FROM daily_allowances da
                    JOIN students s ON da.student_id = s.student_id
                    WHERE da.date = :filter_date ORDER BY s.full_name
                """), {"filter_date": filter_date})
            else:
                result = await session.execute(text("""
                    SELECT da.allowance_id, da.student_id, da.date, da.base_amount, 
                           da.bonus_amount, da.total_amount, s.full_name 
                    FROM daily_allowances da
                    JOIN students s ON da.student_id = s.student_id
                    ORDER BY da.date DESC, s.full_name LIMIT 100
                """))
            rows = result.fetchall()
            columns = ["allowance_id", "student_id", "date", "base_amount", "bonus_amount", "total_amount", "full_name"]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/allowances")
async def set_allowance(data: dict):
    """Set allowance."""
    try:
        base = float(data["base_amount"])
        bonus = float(data.get("bonus_amount", 0))
        
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT allowance_id FROM daily_allowances 
                WHERE student_id = :student_id AND date = :date
            """), {"student_id": data["student_id"], "date": data["date"]})
            existing = result.scalar()
            
            if existing:
                await session.execute(text("""
                    UPDATE daily_allowances SET base_amount=:base, bonus_amount=:bonus, total_amount=:total
                    WHERE student_id=:student_id AND date=:date
                """), {
                    "base": base, "bonus": bonus, "total": base + bonus,
                    "student_id": data["student_id"], "date": data["date"]
                })
            else:
                await session.execute(text("""
                    INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                    VALUES (:allowance_id, :student_id, :date, :base, :bonus, :total)
                """), {
                    "allowance_id": str(uuid.uuid4()),
                    "student_id": data["student_id"],
                    "date": data["date"],
                    "base": base, "bonus": bonus, "total": base + bonus
                })
            await session.commit()
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/allowances/bulk")
async def bulk_allowances(data: dict):
    """Set allowances for all students in a program."""
    try:
        base = float(data["base_amount"])
        bonus = float(data.get("bonus_amount", 0))
        count = 0
        
        async with async_session_factory() as session:
            result = await session.execute(text(
                "SELECT student_id FROM students WHERE program_id = :program_id AND is_active = true"
            ), {"program_id": data["program_id"]})
            students = result.fetchall()
            
            for s in students:
                student_id = s[0]
                
                result = await session.execute(text("""
                    SELECT allowance_id FROM daily_allowances 
                    WHERE student_id = :student_id AND date = :date
                """), {"student_id": student_id, "date": data["date"]})
                existing = result.scalar()
                
                if existing:
                    await session.execute(text("""
                        UPDATE daily_allowances SET base_amount=:base, bonus_amount=:bonus, total_amount=:total
                        WHERE student_id=:student_id AND date=:date
                    """), {
                        "base": base, "bonus": bonus, "total": base + bonus,
                        "student_id": student_id, "date": data["date"]
                    })
                else:
                    await session.execute(text("""
                        INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                        VALUES (:allowance_id, :student_id, :date, :base, :bonus, :total)
                    """), {
                        "allowance_id": str(uuid.uuid4()),
                        "student_id": student_id,
                        "date": data["date"],
                        "base": base, "bonus": bonus, "total": base + bonus
                    })
                count += 1
            
            await session.commit()
        
        return {"success": True, "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== BULK UPLOAD ====================

@router.post("/api/bulk/students")
async def bulk_upload_students(file: UploadFile = File(...), program_id: str = Form(...)):
    """Bulk upload students from CSV."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
            
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        created, errors = 0, []
        
        for row in reader:
            try:
                user_id = str(uuid.uuid4())
                password_hash = hash_password("temp123")
                
                await mongodb.db.users.insert_one({
                    "_id": user_id,
                    "user_id": user_id,
                    "email": row["email"],
                    "name": row["full_name"],
                    "full_name": row["full_name"],
                    "role": "student",
                    "status": "active",
                    "auth": {
                        "password_hash": password_hash,
                        "password_last_changed": datetime.utcnow()
                    },
                    "associations": {"program_id": program_id},
                    "metadata": {
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                })
                
                async with async_session_factory() as session:
                    await session.execute(text("""
                        INSERT INTO students (student_id, user_id, full_name, phone_number, program_id, is_active)
                        VALUES (:student_id, :user_id, :full_name, :phone_number, :program_id, true)
                    """), {
                        "student_id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "full_name": row["full_name"],
                        "phone_number": row.get("phone_number", ""),
                        "program_id": program_id
                    })
                    await session.commit()
                created += 1
            except Exception as e:
                errors.append({"row": row.get("email", "?"), "error": str(e)})
        
        return {"success": True, "created": created, "errors": errors}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/bulk/teachers")
async def bulk_upload_teachers(file: UploadFile = File(...), program_id: str = Form(...)):
    """Bulk upload teachers from CSV."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
            
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        created, errors = 0, []
        
        for row in reader:
            try:
                user_id = str(uuid.uuid4())
                password_hash = hash_password("temp123")
                
                await mongodb.db.users.insert_one({
                    "_id": user_id,
                    "user_id": user_id,
                    "email": row["email"],
                    "name": row["full_name"],
                    "full_name": row["full_name"],
                    "role": "teacher",
                    "status": "active",
                    "auth": {
                        "password_hash": password_hash,
                        "password_last_changed": datetime.utcnow()
                    },
                    "associations": {},
                    "metadata": {
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                })
                
                async with async_session_factory() as session:
                    await session.execute(text("""
                        INSERT INTO teachers (teacher_id, user_id, full_name, employee_id, program_id, is_active)
                        VALUES (:teacher_id, :user_id, :full_name, :employee_id, :program_id, true)
                    """), {
                        "teacher_id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "full_name": row["full_name"],
                        "employee_id": row.get("employee_id", ""),
                        "program_id": program_id
                    })
                    await session.commit()
                created += 1
            except Exception as e:
                errors.append({"row": row.get("email", "?"), "error": str(e)})
        
        return {"success": True, "created": created, "errors": errors}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AUTH ====================

@router.post("/api/auth/login")
async def admin_login(data: dict):
    """Admin login."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
        
        user = await mongodb.db.users.find_one({
            "email": data.get("email"),
            "role": "admin"
        })
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Check if user is active (handle both old 'is_active' and new 'status' field)
        is_active = user.get("is_active", True) if "is_active" in user else user.get("status") == "active"
        if not is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Get password hash from nested auth object or top level
        stored_hash = user.get("auth", {}).get("password_hash") if "auth" in user else user.get("password_hash")
        
        if not stored_hash or not verify_password(data.get("password", ""), stored_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = str(uuid.uuid4())
        
        if redis_client.client is not None:
            await redis_client.client.setex(f"admin_session:{token}", 86400, data.get("email"))
        
        return {
            "success": True,
            "token": token,
            "email": data.get("email"),
            "full_name": user.get("name", user.get("full_name", "Admin"))
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/auth/verify")
async def verify_session(token: str):
    """Verify admin session."""
    try:
        if redis_client.client is not None:
            email = await redis_client.client.get(f"admin_session:{token}")
            if email:
                return {"valid": True, "email": email if isinstance(email, str) else email.decode()}
        return {"valid": False}
    except:
        return {"valid": False}
