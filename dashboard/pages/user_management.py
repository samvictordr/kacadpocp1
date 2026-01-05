"""
User Management Page - Create, view, edit, and manage users.
"""
import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
import uuid
import hashlib

from dashboard.utils.database import (
    get_users_from_mongodb, get_students_from_postgres,
    get_teachers_from_postgres, get_programs_from_postgres,
    get_mongo_db, get_postgres_pool
)


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def create_user(email: str, password: str, name: str, role: str, program_id: str = None):
    """Create a new user in MongoDB and optionally in PostgreSQL."""
    db = get_mongo_db()
    
    # Check if user exists
    existing = await db.users.find_one({"email": email})
    if existing:
        return False, "User with this email already exists"
    
    # Create user in MongoDB
    user_id = str(uuid.uuid4())
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    user_doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "name": name,
        "role": role,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    await db.users.insert_one(user_doc)
    
    # If student or teacher, also add to PostgreSQL
    if role == "student" and program_id:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO students (student_id, user_id, full_name, program_id, is_active)
                VALUES ($1, $2, $3, $4, true)
            """, str(uuid.uuid4()), user_id, name, program_id)
    
    elif role == "teacher" and program_id:
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO teachers (teacher_id, user_id, full_name, program_id, is_active)
                VALUES ($1, $2, $3, $4, true)
            """, str(uuid.uuid4()), user_id, name, program_id)
    
    return True, f"User {name} created successfully"


async def update_user_status(email: str, is_active: bool):
    """Update user active status."""
    db = get_mongo_db()
    result = await db.users.update_one(
        {"email": email},
        {"$set": {"is_active": is_active}}
    )
    return result.modified_count > 0


async def delete_user(email: str):
    """Delete a user."""
    db = get_mongo_db()
    
    # Get user first
    user = await db.users.find_one({"email": email})
    if not user:
        return False, "User not found"
    
    user_id = user.get("user_id")
    role = user.get("role")
    
    # Delete from PostgreSQL if applicable
    pool = await get_postgres_pool()
    async with pool.acquire() as conn:
        if role == "student":
            await conn.execute("DELETE FROM students WHERE user_id = $1", user_id)
        elif role == "teacher":
            await conn.execute("DELETE FROM teachers WHERE user_id = $1", user_id)
    
    # Delete from MongoDB
    await db.users.delete_one({"email": email})
    
    return True, f"User {email} deleted"


def render():
    """Render the user management page."""
    st.markdown('<p class="main-header">👥 User Management</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Create, view, and manage user accounts</p>', unsafe_allow_html=True)
    
    # Tabs for different operations
    tab1, tab2, tab3, tab4 = st.tabs(["📋 All Users", "➕ Create User", "👨‍🎓 Students", "👨‍🏫 Teachers"])
    
    with tab1:
        render_all_users()
    
    with tab2:
        render_create_user()
    
    with tab3:
        render_students()
    
    with tab4:
        render_teachers()


def render_all_users():
    """Render all users list."""
    st.markdown("### All Users (MongoDB)")
    
    # Filter options
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        role_filter = st.selectbox("Filter by Role", ["All", "student", "teacher", "store", "admin"])
    with col2:
        if st.button("🔄 Refresh", key="refresh_users"):
            st.rerun()
    
    try:
        role = None if role_filter == "All" else role_filter
        users = run_async(get_users_from_mongodb(role))
        
        if users:
            # Convert to DataFrame
            df = pd.DataFrame(users)
            display_cols = ["email", "name", "role", "is_active", "created_at"]
            available_cols = [c for c in display_cols if c in df.columns]
            
            st.dataframe(
                df[available_cols],
                use_container_width=True,
                hide_index=True
            )
            
            st.info(f"Total users: {len(users)}")
            
            # User actions
            st.markdown("#### User Actions")
            col1, col2 = st.columns(2)
            
            with col1:
                with st.expander("🔓 Toggle User Status"):
                    email = st.selectbox("Select User", [u["email"] for u in users], key="toggle_user")
                    new_status = st.checkbox("Active", value=True)
                    if st.button("Update Status"):
                        success = run_async(update_user_status(email, new_status))
                        if success:
                            st.success(f"Updated {email}")
                            st.rerun()
                        else:
                            st.error("Failed to update")
            
            with col2:
                with st.expander("🗑️ Delete User"):
                    st.warning("⚠️ This action cannot be undone!")
                    email = st.selectbox("Select User to Delete", [u["email"] for u in users], key="delete_user")
                    confirm = st.text_input("Type 'DELETE' to confirm")
                    if st.button("Delete User", type="primary"):
                        if confirm == "DELETE":
                            success, msg = run_async(delete_user(email))
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("Please type 'DELETE' to confirm")
        else:
            st.info("No users found")
    
    except Exception as e:
        st.error(f"Error loading users: {e}")


def render_create_user():
    """Render create user form."""
    st.markdown("### Create New User")
    
    # Load programs for dropdown
    try:
        programs = run_async(get_programs_from_postgres())
        program_options = {p["name"]: p["program_id"] for p in programs}
    except:
        programs = []
        program_options = {}
    
    with st.form("create_user_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Full Name *", placeholder="John Doe")
            email = st.text_input("Email *", placeholder="john@academy.edu")
            password = st.text_input("Password *", type="password")
        
        with col2:
            role = st.selectbox("Role *", ["student", "teacher", "store", "admin"])
            
            program = None
            if role in ["student", "teacher"]:
                if program_options:
                    program = st.selectbox("Program", list(program_options.keys()))
                else:
                    st.warning("No programs available. Create a program first.")
        
        submitted = st.form_submit_button("Create User", type="primary")
        
        if submitted:
            if not all([name, email, password]):
                st.error("Please fill in all required fields")
            elif role in ["student", "teacher"] and not program:
                st.error("Please select a program for students/teachers")
            else:
                program_id = program_options.get(program) if program else None
                success, msg = run_async(create_user(email, password, name, role, program_id))
                if success:
                    st.success(msg)
                else:
                    st.error(msg)


def render_students():
    """Render students list from PostgreSQL."""
    st.markdown("### Students (PostgreSQL)")
    
    if st.button("🔄 Refresh", key="refresh_students"):
        st.rerun()
    
    try:
        students = run_async(get_students_from_postgres())
        
        if students:
            df = pd.DataFrame(students)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(f"Total students: {len(students)}")
        else:
            st.info("No students found in PostgreSQL")
    
    except Exception as e:
        st.error(f"Error loading students: {e}")


def render_teachers():
    """Render teachers list from PostgreSQL."""
    st.markdown("### Teachers (PostgreSQL)")
    
    if st.button("🔄 Refresh", key="refresh_teachers"):
        st.rerun()
    
    try:
        teachers = run_async(get_teachers_from_postgres())
        
        if teachers:
            df = pd.DataFrame(teachers)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(f"Total teachers: {len(teachers)}")
        else:
            st.info("No teachers found in PostgreSQL")
    
    except Exception as e:
        st.error(f"Error loading teachers: {e}")
