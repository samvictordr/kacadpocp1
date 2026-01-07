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
import re

from app.db.postgres import async_session_factory
from app.db.mongodb import mongodb
from app.db.redis import redis_client
from app.core.security import verify_password, hash_password

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ==================== PHONE VALIDATION ====================

def validate_saudi_phone(phone: str) -> tuple[bool, str]:
    """
    Validate Saudi Arabian phone number.
    Accepted formats:
    - +966XXXXXXXXX (9 digits after country code)
    - 05XXXXXXXX (10 digits starting with 05)
    Returns normalized format: +966XXXXXXXXX
    """
    if not phone or phone.strip() == "":
        return True, ""  # Empty phone is allowed
    
    phone = phone.strip().replace(" ", "").replace("-", "")
    
    # Pattern for +966 format
    if phone.startswith("+966"):
        digits = phone[4:]
        if len(digits) == 9 and digits.isdigit() and digits[0] == "5":
            return True, phone
        return False, "Invalid Saudi phone: must be +966 followed by 9 digits starting with 5"
    
    # Pattern for 05 format
    if phone.startswith("05"):
        if len(phone) == 10 and phone.isdigit():
            return True, "+966" + phone[1:]  # Convert to international format
        return False, "Invalid Saudi phone: must be 10 digits starting with 05"
    
    # Pattern for 5 format (without leading 0)
    if phone.startswith("5") and len(phone) == 9 and phone.isdigit():
        return True, "+966" + phone
    
    return False, "Invalid Saudi phone format. Use +966XXXXXXXXX or 05XXXXXXXX"


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
                WHERE DATE(transaction_time) = CURRENT_DATE
            """))
            stats["transactions_today"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COALESCE(SUM(total_amount), 0) FROM store_transactions 
                WHERE DATE(transaction_time) = CURRENT_DATE
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
                SELECT COUNT(*) FROM store_transactions WHERE DATE(transaction_time) = CURRENT_DATE
            """))
            metrics["transactions"]["today"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM store_transactions WHERE transaction_time >= CURRENT_DATE - INTERVAL '7 days'
            """))
            metrics["transactions"]["week"] = result.scalar() or 0
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM store_transactions WHERE transaction_time >= CURRENT_DATE - INTERVAL '30 days'
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
                SELECT DATE(transaction_time) as date, COUNT(*) as count,
                       COALESCE(SUM(total_amount), 0) as total
                FROM store_transactions
                WHERE transaction_time >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(transaction_time) ORDER BY date
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
    """Get all teachers with their program assignments."""
    try:
        async with async_session_factory() as session:
            # Get basic teacher info
            result = await session.execute(text("""
                SELECT t.teacher_id, t.user_id, t.full_name, t.is_active
                FROM teachers t ORDER BY t.full_name
            """))
            rows = result.fetchall()
            teachers = []
            
            for row in rows:
                teacher_id = str(row[0])
                # Get all programs for this teacher from junction table
                prog_result = await session.execute(text("""
                    SELECT p.program_id, p.name 
                    FROM teacher_programs tp
                    JOIN programs p ON tp.program_id = p.program_id
                    WHERE tp.teacher_id = :teacher_id
                """), {"teacher_id": teacher_id})
                prog_rows = prog_result.fetchall()
                
                programs = [{"program_id": str(pr[0]), "name": pr[1]} for pr in prog_rows]
                program_names = ", ".join([p["name"] for p in programs]) if programs else "No programs"
                
                teachers.append({
                    "teacher_id": teacher_id,
                    "user_id": str(row[1]),
                    "full_name": row[2],
                    "is_active": row[3],
                    "programs": programs,
                    "program_name": program_names  # For backward compatibility with UI
                })
            
            return teachers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/programs")
async def get_all_programs():
    """Get all programs."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT p.program_id, p.name, p.cost_center, 
                       p.default_daily_allowance, p.is_active,
                       p.start_date, p.end_date,
                       COUNT(DISTINCT s.student_id) as student_count,
                       COUNT(DISTINCT tp.teacher_id) as teacher_count
                FROM programs p
                LEFT JOIN students s ON p.program_id = s.program_id AND s.is_active = true
                LEFT JOIN teacher_programs tp ON p.program_id = tp.program_id
                LEFT JOIN teachers t ON tp.teacher_id = t.teacher_id AND t.is_active = true
                GROUP BY p.program_id ORDER BY p.name
            """))
            rows = result.fetchall()
            columns = ["program_id", "name", "cost_center", "default_daily_allowance", "is_active", "start_date", "end_date", "student_count", "teacher_count"]
            programs = [dict(zip(columns, row)) for row in rows]
            # Convert dates to strings
            for prog in programs:
                if prog.get("start_date"):
                    prog["start_date"] = str(prog["start_date"])
                if prog.get("end_date"):
                    prog["end_date"] = str(prog["end_date"])
            return programs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/users")
async def create_user(data: dict):
    """Create a new user."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
        
        role = data["role"]
        
        # Validate phone number for students
        phone_number = data.get("phone_number", "")
        if role == "student" and phone_number:
            is_valid, normalized = validate_saudi_phone(phone_number)
            if not is_valid:
                raise HTTPException(status_code=400, detail=normalized)
            phone_number = normalized
            
            # Check uniqueness
            async with async_session_factory() as session:
                result = await session.execute(text(
                    "SELECT student_id FROM students WHERE phone_number = :phone"
                ), {"phone": phone_number})
                if result.scalar():
                    raise HTTPException(status_code=400, detail="Phone number already registered")
            
        user_id = str(uuid.uuid4())
        password_hash = hash_password(data.get("password", "temp123"))
        
        await mongodb.db.users.insert_one({
            "_id": user_id,
            "user_id": user_id,
            "email": data["email"],
            "name": data["full_name"],
            "full_name": data["full_name"],
            "role": role,
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
            if role == "student":
                student_id = str(uuid.uuid4())
                await session.execute(text("""
                    INSERT INTO students (student_id, user_id, full_name, phone_number, program_id, is_active)
                    VALUES (:student_id, :user_id, :full_name, :phone_number, :program_id, true)
                """), {
                    "student_id": student_id,
                    "user_id": user_id,
                    "full_name": data["full_name"],
                    "phone_number": phone_number or None,
                    "program_id": data.get("program_id")
                })
                
                # Enroll student in class if class_id provided
                class_id = data.get("class_id")
                if class_id:
                    await session.execute(text("""
                        INSERT INTO class_enrollments (class_id, student_id)
                        VALUES (:class_id, :student_id)
                        ON CONFLICT (class_id, student_id) DO NOTHING
                    """), {
                        "class_id": class_id,
                        "student_id": student_id
                    })
            elif role == "teacher":
                teacher_id = str(uuid.uuid4())
                # Get first program_id for backward compatibility (legacy column)
                program_ids = data.get("program_ids", [])
                primary_program_id = program_ids[0] if program_ids else data.get("program_id")
                
                await session.execute(text("""
                    INSERT INTO teachers (teacher_id, user_id, full_name, program_id, is_active, created_at)
                    VALUES (:teacher_id, :user_id, :full_name, :program_id, true, NOW())
                """), {
                    "teacher_id": teacher_id,
                    "user_id": user_id,
                    "full_name": data["full_name"],
                    "program_id": primary_program_id
                })
                
                # Insert into teacher_programs junction table for all selected programs
                for program_id in program_ids:
                    await session.execute(text("""
                        INSERT INTO teacher_programs (teacher_id, program_id)
                        VALUES (:teacher_id, :program_id)
                        ON CONFLICT (teacher_id, program_id) DO NOTHING
                    """), {
                        "teacher_id": teacher_id,
                        "program_id": program_id
                    })
            # Store users only get MongoDB entry, no PostgreSQL record needed
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
    """Delete a user and all related records."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
        
        async with async_session_factory() as session:
            # First get the student_id if this is a student
            result = await session.execute(text(
                "SELECT student_id FROM students WHERE user_id = :user_id"
            ), {"user_id": user_id})
            student_row = result.fetchone()
            
            if student_row:
                student_id = str(student_row[0])
                
                # Delete in FK-safe order for student-related tables
                # 1. Delete attendance records (references students via session, but also directly)
                await session.execute(text(
                    "DELETE FROM attendance_records WHERE student_id = :student_id"
                ), {"student_id": student_id})
                
                # 2. Delete class enrollments
                await session.execute(text(
                    "DELETE FROM class_enrollments WHERE student_id = :student_id"
                ), {"student_id": student_id})
                
                # 3. Delete store transactions
                await session.execute(text(
                    "DELETE FROM store_transactions WHERE student_id = :student_id"
                ), {"student_id": student_id})
                
                # 4. Delete daily allowances
                await session.execute(text(
                    "DELETE FROM daily_allowances WHERE student_id = :student_id"
                ), {"student_id": student_id})
                
                # 5. Finally delete the student record
                await session.execute(text(
                    "DELETE FROM students WHERE user_id = :user_id"
                ), {"user_id": user_id})
            
            # Check if this is a teacher
            result = await session.execute(text(
                "SELECT teacher_id FROM teachers WHERE user_id = :user_id"
            ), {"user_id": user_id})
            teacher_row = result.fetchone()
            
            if teacher_row:
                teacher_id = str(teacher_row[0])
                
                # Delete teacher-related records
                # 1. Delete teacher meal transactions
                await session.execute(text(
                    "DELETE FROM teacher_meal_transactions WHERE teacher_id = :teacher_id"
                ), {"teacher_id": teacher_id})
                
                # 2. Delete teacher daily allowances
                await session.execute(text(
                    "DELETE FROM teacher_daily_allowances WHERE teacher_id = :teacher_id"
                ), {"teacher_id": teacher_id})
                
                # 3. Delete teacher program associations
                await session.execute(text(
                    "DELETE FROM teacher_programs WHERE teacher_id = :teacher_id"
                ), {"teacher_id": teacher_id})
                
                # 4. Delete attendance sessions created by this teacher
                await session.execute(text(
                    "DELETE FROM attendance_records WHERE session_id IN (SELECT session_id FROM attendance_sessions WHERE created_by = :user_id)"
                ), {"user_id": user_id})
                await session.execute(text(
                    "DELETE FROM attendance_sessions WHERE created_by = :user_id"
                ), {"user_id": user_id})
                
                # 5. Update classes to remove teacher reference or delete them
                await session.execute(text(
                    "DELETE FROM class_enrollments WHERE class_id IN (SELECT class_id FROM classes WHERE teacher_id = :teacher_id)"
                ), {"teacher_id": teacher_id})
                await session.execute(text(
                    "DELETE FROM classes WHERE teacher_id = :teacher_id"
                ), {"teacher_id": teacher_id})
                
                # 6. Finally delete the teacher record
                await session.execute(text(
                    "DELETE FROM teachers WHERE user_id = :user_id"
                ), {"user_id": user_id})
            
            await session.commit()
        
        # Delete from MongoDB
        await mongodb.db.users.delete_one({"user_id": user_id})
        
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
        cost_center = data.get("cost_center", data.get("cost_center_code", "GEN-001"))
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        
        async with async_session_factory() as session:
            await session.execute(text("""
                INSERT INTO programs (program_id, name, cost_center_code, cost_center, default_daily_allowance, start_date, end_date, is_active, active)
                VALUES (:program_id, :name, :cost_center_code, :cost_center, :default_daily_allowance, :start_date, :end_date, true, true)
            """), {
                "program_id": program_id,
                "name": data["name"],
                "cost_center_code": cost_center,
                "cost_center": cost_center,
                "default_daily_allowance": float(data.get("default_daily_allowance", 50.0)),
                "start_date": start_date,
                "end_date": end_date
            })
            await session.commit()
        
        return {"success": True, "program_id": program_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/programs/{program_id}")
async def update_program(program_id: str, data: dict):
    """Update a program."""
    try:
        cost_center = data.get("cost_center", data.get("cost_center_code", "GEN-001"))
        is_active = data.get("is_active", True)
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        
        async with async_session_factory() as session:
            # Check if program is being deactivated
            result = await session.execute(text(
                "SELECT is_active FROM programs WHERE program_id = :program_id"
            ), {"program_id": program_id})
            current_active = result.scalar()
            
            # Update program
            await session.execute(text("""
                UPDATE programs SET name = :name, cost_center = :cost_center, cost_center_code = :cost_center_code,
                default_daily_allowance = :default_daily_allowance, start_date = :start_date, end_date = :end_date,
                is_active = :is_active, active = :active 
                WHERE program_id = :program_id
            """), {
                "name": data["name"],
                "cost_center": cost_center,
                "cost_center_code": cost_center,
                "default_daily_allowance": float(data.get("default_daily_allowance", 50.0)),
                "start_date": start_date,
                "end_date": end_date,
                "is_active": is_active,
                "active": is_active,
                "program_id": program_id
            })
            
            # If program is being deactivated, deactivate associated students and teachers
            if current_active and not is_active:
                # Deactivate students
                await session.execute(text("""
                    UPDATE students SET is_active = false 
                    WHERE program_id = :program_id AND is_active = true
                """), {"program_id": program_id})
                
                # Deactivate teachers via teacher_programs junction table
                result = await session.execute(text("""
                    SELECT teacher_id FROM teacher_programs WHERE program_id = :program_id
                """), {"program_id": program_id})
                teacher_ids = [row[0] for row in result.fetchall()]
                
                for teacher_id in teacher_ids:
                    # Check if teacher has other active programs
                    result = await session.execute(text("""
                        SELECT COUNT(*) FROM teacher_programs tp
                        JOIN programs p ON tp.program_id = p.program_id
                        WHERE tp.teacher_id = :teacher_id AND p.is_active = true AND p.program_id != :program_id
                    """), {"teacher_id": teacher_id, "program_id": program_id})
                    other_active_programs = result.scalar() or 0
                    
                    # Only deactivate teacher if they have no other active programs
                    if other_active_programs == 0:
                        await session.execute(text("""
                            UPDATE teachers SET is_active = false WHERE teacher_id = :teacher_id
                        """), {"teacher_id": teacher_id})
                
                # Also update MongoDB users
                student_user_ids = await session.execute(text("""
                    SELECT user_id FROM students WHERE program_id = :program_id
                """), {"program_id": program_id})
                for row in student_user_ids:
                    await mongodb.db.users.update_one(
                        {"user_id": str(row[0])},
                        {"$set": {"status": "inactive"}}
                    )
                
                teacher_user_ids = await session.execute(text("""
                    SELECT user_id FROM teachers WHERE teacher_id = ANY(:teacher_ids)
                """), {"teacher_ids": teacher_ids})
                for row in teacher_user_ids:
                    await mongodb.db.users.update_one(
                        {"user_id": str(row[0])},
                        {"$set": {"status": "inactive"}}
                    )
            
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


@router.post("/api/programs/check-expired")
async def check_expired_programs():
    """Check and auto-deactivate programs that have exceeded their end date."""
    try:
        from datetime import date
        today = date.today()
        
        async with async_session_factory() as session:
            # Find active programs with end_date in the past
            result = await session.execute(text("""
                SELECT program_id FROM programs 
                WHERE is_active = true AND end_date IS NOT NULL AND end_date < :today
            """), {"today": today})
            expired_program_ids = [row[0] for row in result.fetchall()]
            
            deactivated_count = 0
            for program_id in expired_program_ids:
                # Deactivate program
                await session.execute(text("""
                    UPDATE programs SET is_active = false, active = false 
                    WHERE program_id = :program_id
                """), {"program_id": str(program_id)})
                
                # Deactivate students
                await session.execute(text("""
                    UPDATE students SET is_active = false 
                    WHERE program_id = :program_id AND is_active = true
                """), {"program_id": str(program_id)})
                
                # Deactivate teachers (only if they have no other active programs)
                result = await session.execute(text("""
                    SELECT teacher_id FROM teacher_programs WHERE program_id = :program_id
                """), {"program_id": str(program_id)})
                teacher_ids = [row[0] for row in result.fetchall()]
                
                for teacher_id in teacher_ids:
                    result = await session.execute(text("""
                        SELECT COUNT(*) FROM teacher_programs tp
                        JOIN programs p ON tp.program_id = p.program_id
                        WHERE tp.teacher_id = :teacher_id AND p.is_active = true
                    """), {"teacher_id": str(teacher_id)})
                    other_active_programs = result.scalar() or 0
                    
                    if other_active_programs == 0:
                        await session.execute(text("""
                            UPDATE teachers SET is_active = false WHERE teacher_id = :teacher_id
                        """), {"teacher_id": str(teacher_id)})
                
                # Update MongoDB users
                student_user_ids = await session.execute(text("""
                    SELECT user_id FROM students WHERE program_id = :program_id
                """), {"program_id": str(program_id)})
                for row in student_user_ids:
                    await mongodb.db.users.update_one(
                        {"user_id": str(row[0])},
                        {"$set": {"status": "inactive"}}
                    )
                
                if teacher_ids:
                    teacher_user_ids = await session.execute(text("""
                        SELECT user_id FROM teachers WHERE teacher_id = ANY(:teacher_ids)
                    """), {"teacher_ids": [str(tid) for tid in teacher_ids]})
                    for row in teacher_user_ids:
                        await mongodb.db.users.update_one(
                            {"user_id": str(row[0])},
                            {"$set": {"status": "inactive"}}
                        )
                
                deactivated_count += 1
            
            await session.commit()
        
        return {
            "success": True, 
            "deactivated_count": deactivated_count,
            "program_ids": [str(pid) for pid in expired_program_ids]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CLASSES ====================

@router.get("/api/classes")
async def get_all_classes(program_id: Optional[str] = None):
    """Get all classes, optionally filtered by program."""
    try:
        async with async_session_factory() as session:
            if program_id:
                result = await session.execute(text("""
                    SELECT c.class_id, c.name, c.program_id, c.teacher_id, c.active,
                           p.name as program_name, t.full_name as teacher_name
                    FROM classes c
                    LEFT JOIN programs p ON c.program_id = p.program_id
                    LEFT JOIN teachers t ON c.teacher_id = t.user_id
                    WHERE c.program_id = :program_id
                    ORDER BY p.name, c.name
                """), {"program_id": program_id})
            else:
                result = await session.execute(text("""
                    SELECT c.class_id, c.name, c.program_id, c.teacher_id, c.active,
                           p.name as program_name, t.full_name as teacher_name
                    FROM classes c
                    LEFT JOIN programs p ON c.program_id = p.program_id
                    LEFT JOIN teachers t ON c.teacher_id = t.user_id
                    ORDER BY p.name, c.name
                """))
            rows = result.fetchall()
            columns = ["class_id", "name", "program_id", "teacher_id", "active", "program_name", "teacher_name"]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/classes")
async def create_class(data: dict):
    """Create a new class."""
    try:
        class_id = str(uuid.uuid4())
        async with async_session_factory() as session:
            await session.execute(text("""
                INSERT INTO classes (class_id, name, program_id, teacher_id, active)
                VALUES (:class_id, :name, :program_id, :teacher_id, true)
            """), {
                "class_id": class_id,
                "name": data["name"],
                "program_id": data["program_id"],
                "teacher_id": data["teacher_id"]
            })
            await session.commit()
        return {"success": True, "class_id": class_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/classes/{class_id}")
async def delete_class(class_id: str):
    """Delete a class."""
    try:
        async with async_session_factory() as session:
            # Check for enrollments
            result = await session.execute(text(
                "SELECT COUNT(*) FROM class_enrollments WHERE class_id = :class_id"
            ), {"class_id": class_id})
            enrollment_count = result.scalar()
            
            if enrollment_count > 0:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete class with {enrollment_count} enrolled students. Remove enrollments first."
                )
            
            # Check for attendance sessions
            result = await session.execute(text(
                "SELECT COUNT(*) FROM attendance_sessions WHERE class_id = :class_id"
            ), {"class_id": class_id})
            session_count = result.scalar()
            
            if session_count > 0:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete class with {session_count} attendance sessions. Archive it instead."
                )
            
            await session.execute(text(
                "DELETE FROM classes WHERE class_id = :class_id"
            ), {"class_id": class_id})
            await session.commit()
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ALLOWANCES ====================

@router.get("/api/allowances")
async def get_allowances(filter_date: Optional[str] = None, user_type: Optional[str] = None):
    """Get allowances for students and/or teachers."""
    try:
        results = []
        async with async_session_factory() as session:
            # Get student allowances (unless user_type is 'teacher')
            if user_type != 'teacher':
                if filter_date:
                    result = await session.execute(text("""
                        SELECT da.allowance_id, da.student_id as user_id, da.date, da.base_amount, 
                               da.bonus_amount, da.total_amount, s.full_name, 'student' as user_type
                        FROM daily_allowances da
                        JOIN students s ON da.student_id = s.student_id
                        WHERE da.date = :filter_date ORDER BY s.full_name
                    """), {"filter_date": filter_date})
                else:
                    result = await session.execute(text("""
                        SELECT da.allowance_id, da.student_id as user_id, da.date, da.base_amount, 
                               da.bonus_amount, da.total_amount, s.full_name, 'student' as user_type
                        FROM daily_allowances da
                        JOIN students s ON da.student_id = s.student_id
                        ORDER BY da.date DESC, s.full_name LIMIT 100
                    """))
                rows = result.fetchall()
                columns = ["allowance_id", "user_id", "date", "base_amount", "bonus_amount", "total_amount", "full_name", "user_type"]
                results.extend([dict(zip(columns, row)) for row in rows])
            
            # Get teacher allowances (unless user_type is 'student')
            if user_type != 'student':
                if filter_date:
                    result = await session.execute(text("""
                        SELECT tda.allowance_id, tda.teacher_id as user_id, tda.date, tda.base_amount, 
                               tda.bonus_amount, tda.total_amount, t.full_name, 'teacher' as user_type
                        FROM teacher_daily_allowances tda
                        JOIN teachers t ON tda.teacher_id = t.teacher_id
                        WHERE tda.date = :filter_date ORDER BY t.full_name
                    """), {"filter_date": filter_date})
                else:
                    result = await session.execute(text("""
                        SELECT tda.allowance_id, tda.teacher_id as user_id, tda.date, tda.base_amount, 
                               tda.bonus_amount, tda.total_amount, t.full_name, 'teacher' as user_type
                        FROM teacher_daily_allowances tda
                        JOIN teachers t ON tda.teacher_id = t.teacher_id
                        ORDER BY tda.date DESC, t.full_name LIMIT 100
                    """))
                rows = result.fetchall()
                columns = ["allowance_id", "user_id", "date", "base_amount", "bonus_amount", "total_amount", "full_name", "user_type"]
                results.extend([dict(zip(columns, row)) for row in rows])
            
            # Sort combined results by date desc, then name
            results.sort(key=lambda x: (str(x['date']), x['full_name']), reverse=True)
            return results[:100]  # Limit to 100 total
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/allowances")
async def set_allowance(data: dict):
    """Set allowance."""
    try:
        base = float(data["base_amount"])
        bonus = float(data.get("bonus_amount", 0))
        # Convert date string to date object if needed
        allowance_date = data["date"]
        if isinstance(allowance_date, str):
            from datetime import date as date_type
            allowance_date = date_type.fromisoformat(allowance_date)
        
        async with async_session_factory() as session:
            result = await session.execute(text("""
                SELECT allowance_id FROM daily_allowances 
                WHERE student_id = :student_id AND date = :date
            """), {"student_id": data["student_id"], "date": allowance_date})
            existing = result.scalar()
            
            if existing:
                await session.execute(text("""
                    UPDATE daily_allowances SET base_amount=:base, bonus_amount=:bonus, total_amount=:total
                    WHERE student_id=:student_id AND date=:date
                """), {
                    "base": base, "bonus": bonus, "total": base + bonus,
                    "student_id": data["student_id"], "date": allowance_date
                })
            else:
                await session.execute(text("""
                    INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                    VALUES (:allowance_id, :student_id, :date, :base, :bonus, :total)
                """), {
                    "allowance_id": str(uuid.uuid4()),
                    "student_id": data["student_id"],
                    "date": allowance_date,
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
        # Convert date string to date object if needed
        allowance_date = data["date"]
        if isinstance(allowance_date, str):
            from datetime import date as date_type
            allowance_date = date_type.fromisoformat(allowance_date)
        
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
                """), {"student_id": student_id, "date": allowance_date})
                existing = result.scalar()
                
                if existing:
                    await session.execute(text("""
                        UPDATE daily_allowances SET base_amount=:base, bonus_amount=:bonus, total_amount=:total
                        WHERE student_id=:student_id AND date=:date
                    """), {
                        "base": base, "bonus": bonus, "total": base + bonus,
                        "student_id": student_id, "date": allowance_date
                    })
                else:
                    await session.execute(text("""
                        INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                        VALUES (:allowance_id, :student_id, :date, :base, :bonus, :total)
                    """), {
                        "allowance_id": str(uuid.uuid4()),
                        "student_id": student_id,
                        "date": allowance_date,
                        "base": base, "bonus": bonus, "total": base + bonus
                    })
                count += 1
            
            await session.commit()
        
        return {"success": True, "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/supplements")
async def add_supplement(data: dict):
    """
    Add a supplement (bonus) to an existing allowance.
    This adds to the current bonus_amount without changing base_amount.
    Works for both students and teachers.
    """
    try:
        from datetime import date as date_type
        
        target_type = data.get("type", "student")  # "student" or "teacher"
        target_id = data["target_id"]
        supplement_amount = float(data["amount"])
        supplement_date = data.get("date", str(date_type.today()))
        
        if isinstance(supplement_date, str):
            supplement_date = date_type.fromisoformat(supplement_date)
        
        async with async_session_factory() as session:
            if target_type == "student":
                # Check if allowance exists for this date
                result = await session.execute(text("""
                    SELECT allowance_id, base_amount, bonus_amount 
                    FROM daily_allowances 
                    WHERE student_id = :target_id AND date = :date
                """), {"target_id": target_id, "date": supplement_date})
                existing = result.fetchone()
                
                if existing:
                    new_bonus = float(existing[2]) + supplement_amount
                    new_total = float(existing[1]) + new_bonus
                    await session.execute(text("""
                        UPDATE daily_allowances 
                        SET bonus_amount = :bonus, total_amount = :total
                        WHERE student_id = :target_id AND date = :date
                    """), {
                        "bonus": new_bonus, "total": new_total,
                        "target_id": target_id, "date": supplement_date
                    })
                else:
                    # Create new allowance with supplement only
                    await session.execute(text("""
                        INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                        VALUES (:allowance_id, :target_id, :date, 0, :bonus, :bonus)
                    """), {
                        "allowance_id": str(uuid.uuid4()),
                        "target_id": target_id,
                        "date": supplement_date,
                        "bonus": supplement_amount
                    })
            else:  # teacher
                result = await session.execute(text("""
                    SELECT allowance_id, base_amount, bonus_amount 
                    FROM teacher_daily_allowances 
                    WHERE teacher_id = :target_id AND date = :date
                """), {"target_id": target_id, "date": supplement_date})
                existing = result.fetchone()
                
                if existing:
                    new_bonus = float(existing[2]) + supplement_amount
                    new_total = float(existing[1]) + new_bonus
                    await session.execute(text("""
                        UPDATE teacher_daily_allowances 
                        SET bonus_amount = :bonus, total_amount = :total
                        WHERE teacher_id = :target_id AND date = :date
                    """), {
                        "bonus": new_bonus, "total": new_total,
                        "target_id": target_id, "date": supplement_date
                    })
                else:
                    await session.execute(text("""
                        INSERT INTO teacher_daily_allowances (allowance_id, teacher_id, date, base_amount, bonus_amount, total_amount)
                        VALUES (:allowance_id, :target_id, :date, 0, :bonus, :bonus)
                    """), {
                        "allowance_id": str(uuid.uuid4()),
                        "target_id": target_id,
                        "date": supplement_date,
                        "bonus": supplement_amount
                    })
            
            await session.commit()
        
        return {"success": True, "message": f"Supplement of {supplement_amount} SAR added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== BULK UPLOAD ====================

@router.post("/api/bulk/students")
async def bulk_upload_students(
    file: UploadFile = File(...), 
    program_id: str = Form(...),
    class_id: Optional[str] = Form(None)
):
    """Bulk upload students from CSV. Optionally enroll all in a class."""
    try:
        if mongodb.db is None:
            raise HTTPException(status_code=503, detail="MongoDB not connected")
            
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        
        created, errors = 0, []
        
        for row in reader:
            try:
                # Validate phone number
                phone_number = row.get("phone_number", "")
                if phone_number:
                    is_valid, result = validate_saudi_phone(phone_number)
                    if not is_valid:
                        errors.append({"row": row.get("email", "?"), "error": result})
                        continue
                    phone_number = result
                
                user_id = str(uuid.uuid4())
                student_id = str(uuid.uuid4())
                password_hash = hash_password("temp123")
                
                # Check if CSV row has a class_id column (overrides form class_id)
                row_class_id = row.get("class_id", "").strip() or class_id
                
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
                        "student_id": student_id,
                        "user_id": user_id,
                        "full_name": row["full_name"],
                        "phone_number": phone_number or None,
                        "program_id": program_id
                    })
                    
                    # Enroll in class if class_id provided
                    if row_class_id:
                        await session.execute(text("""
                            INSERT INTO class_enrollments (class_id, student_id)
                            VALUES (:class_id, :student_id)
                            ON CONFLICT (class_id, student_id) DO NOTHING
                        """), {
                            "class_id": row_class_id,
                            "student_id": student_id
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
                        INSERT INTO teachers (teacher_id, user_id, full_name, program_id, is_active, created_at)
                        VALUES (:teacher_id, :user_id, :full_name, :program_id, true, NOW())
                    """), {
                        "teacher_id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "full_name": row["full_name"],
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
