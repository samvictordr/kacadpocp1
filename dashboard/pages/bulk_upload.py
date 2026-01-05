"""
Bulk Upload Page - Upload users from CSV or Excel files.
"""
import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
import uuid
import hashlib
import io

from dashboard.utils.database import (
    get_mongo_db, get_postgres_pool, get_programs_from_postgres
)


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def bulk_create_students(data: pd.DataFrame, program_id: str, default_password: str = "student123"):
    """Bulk create student accounts."""
    db = get_mongo_db()
    pool = await get_postgres_pool()
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }
    
    for idx, row in data.iterrows():
        try:
            email = str(row.get("email", "")).strip()
            name = str(row.get("full_name", row.get("name", ""))).strip()
            password = str(row.get("password", default_password)).strip()
            
            if not email or not name:
                results["errors"].append(f"Row {idx + 1}: Missing email or name")
                results["failed"] += 1
                continue
            
            # Check if user exists
            existing = await db.users.find_one({"email": email})
            if existing:
                results["errors"].append(f"Row {idx + 1}: Email {email} already exists")
                results["failed"] += 1
                continue
            
            # Create user in MongoDB
            user_id = str(uuid.uuid4())
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            user_doc = {
                "user_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "name": name,
                "role": "student",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "created_via": "bulk_upload"
            }
            
            await db.users.insert_one(user_doc)
            
            # Create student in PostgreSQL
            student_id = str(uuid.uuid4())
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO students (student_id, user_id, full_name, program_id, is_active)
                    VALUES ($1, $2, $3, $4, true)
                """, student_id, user_id, name, program_id)
            
            results["success"] += 1
            
        except Exception as e:
            results["errors"].append(f"Row {idx + 1}: {str(e)}")
            results["failed"] += 1
    
    return results


async def bulk_create_teachers(data: pd.DataFrame, program_id: str, default_password: str = "teacher123"):
    """Bulk create teacher accounts."""
    db = get_mongo_db()
    pool = await get_postgres_pool()
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }
    
    for idx, row in data.iterrows():
        try:
            email = str(row.get("email", "")).strip()
            name = str(row.get("full_name", row.get("name", ""))).strip()
            password = str(row.get("password", default_password)).strip()
            
            if not email or not name:
                results["errors"].append(f"Row {idx + 1}: Missing email or name")
                results["failed"] += 1
                continue
            
            # Check if user exists
            existing = await db.users.find_one({"email": email})
            if existing:
                results["errors"].append(f"Row {idx + 1}: Email {email} already exists")
                results["failed"] += 1
                continue
            
            # Create user in MongoDB
            user_id = str(uuid.uuid4())
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            user_doc = {
                "user_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "name": name,
                "role": "teacher",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "created_via": "bulk_upload"
            }
            
            await db.users.insert_one(user_doc)
            
            # Create teacher in PostgreSQL
            teacher_id = str(uuid.uuid4())
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO teachers (teacher_id, user_id, full_name, program_id, is_active)
                    VALUES ($1, $2, $3, $4, true)
                """, teacher_id, user_id, name, program_id)
            
            results["success"] += 1
            
        except Exception as e:
            results["errors"].append(f"Row {idx + 1}: {str(e)}")
            results["failed"] += 1
    
    return results


async def bulk_create_store_staff(data: pd.DataFrame, default_password: str = "store123"):
    """Bulk create store staff accounts."""
    db = get_mongo_db()
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }
    
    for idx, row in data.iterrows():
        try:
            email = str(row.get("email", "")).strip()
            name = str(row.get("full_name", row.get("name", ""))).strip()
            password = str(row.get("password", default_password)).strip()
            
            if not email or not name:
                results["errors"].append(f"Row {idx + 1}: Missing email or name")
                results["failed"] += 1
                continue
            
            # Check if user exists
            existing = await db.users.find_one({"email": email})
            if existing:
                results["errors"].append(f"Row {idx + 1}: Email {email} already exists")
                results["failed"] += 1
                continue
            
            # Create user in MongoDB
            user_id = str(uuid.uuid4())
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            user_doc = {
                "user_id": user_id,
                "email": email,
                "password_hash": password_hash,
                "name": name,
                "role": "store",
                "is_active": True,
                "created_at": datetime.utcnow(),
                "created_via": "bulk_upload"
            }
            
            await db.users.insert_one(user_doc)
            results["success"] += 1
            
        except Exception as e:
            results["errors"].append(f"Row {idx + 1}: {str(e)}")
            results["failed"] += 1
    
    return results


def render():
    """Render the bulk upload page."""
    st.markdown('<p class="main-header">📤 Bulk Upload</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Upload students, teachers, or store staff from CSV/Excel files</p>', unsafe_allow_html=True)
    
    # Instructions
    with st.expander("📖 File Format Instructions", expanded=False):
        st.markdown("""
        ### Required File Format
        
        Your CSV or Excel file must contain the following columns:
        
        | Column | Required | Description |
        |--------|----------|-------------|
        | `email` | ✅ Yes | User's email address (must be unique) |
        | `full_name` or `name` | ✅ Yes | User's full name |
        | `password` | ❌ Optional | Password (defaults to role-based: student123, teacher123, store123) |
        
        #### Example CSV:
        ```csv
        email,full_name,password
        john.doe@academy.edu,John Doe,mypassword123
        jane.smith@academy.edu,Jane Smith,
        bob.wilson@academy.edu,Bob Wilson,securepass
        ```
        
        **Notes:**
        - If password is empty, a default password will be used
        - Emails must be unique - duplicates will be skipped
        - Names should not contain special characters
        
        📄 See `bulkuploadformats.md` for detailed format specifications.
        """)
    
    st.markdown("---")
    
    # Upload type selection
    col1, col2 = st.columns([1, 2])
    
    with col1:
        upload_type = st.radio(
            "Select User Type",
            ["👨‍🎓 Students", "👨‍🏫 Teachers", "🏪 Store Staff"],
            label_visibility="visible"
        )
    
    with col2:
        # File upload
        uploaded_file = st.file_uploader(
            "Upload CSV or Excel File",
            type=["csv", "xlsx", "xls"],
            help="Upload a CSV or Excel file with user data"
        )
    
    if uploaded_file:
        # Parse file
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ File loaded: {len(df)} rows")
            
            # Preview
            st.markdown("### Preview Data")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Validation
            st.markdown("### Validation")
            errors = []
            
            # Check required columns
            required_cols = ["email"]
            name_col = "full_name" if "full_name" in df.columns else ("name" if "name" in df.columns else None)
            
            if not name_col:
                errors.append("Missing 'full_name' or 'name' column")
            
            for col in required_cols:
                if col not in df.columns:
                    errors.append(f"Missing required column: {col}")
            
            # Check for empty values
            if name_col and df[name_col].isnull().any():
                errors.append("Some rows have empty names")
            
            if "email" in df.columns and df["email"].isnull().any():
                errors.append("Some rows have empty emails")
            
            # Check for duplicates
            if "email" in df.columns:
                duplicates = df["email"].duplicated().sum()
                if duplicates > 0:
                    errors.append(f"{duplicates} duplicate emails in file")
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                st.success("✅ File validation passed")
            
            st.markdown("---")
            
            # Program selection for students/teachers
            program_id = None
            if upload_type in ["👨‍🎓 Students", "👨‍🏫 Teachers"]:
                try:
                    programs = run_async(get_programs_from_postgres())
                    program_options = {p["name"]: p["program_id"] for p in programs}
                    
                    if program_options:
                        program = st.selectbox("Select Program", list(program_options.keys()))
                        program_id = program_options[program]
                    else:
                        st.error("No programs available. Please create a program first.")
                        return
                except Exception as e:
                    st.error(f"Error loading programs: {e}")
                    return
            
            # Default password
            default_password = st.text_input(
                "Default Password (for rows without password)",
                value="student123" if "Student" in upload_type else ("teacher123" if "Teacher" in upload_type else "store123"),
                type="password"
            )
            
            # Upload button
            st.markdown("---")
            
            col1, col2, col3 = st.columns([2, 1, 2])
            with col2:
                if st.button("🚀 Start Upload", type="primary", use_container_width=True, disabled=len(errors) > 0):
                    with st.spinner("Uploading users..."):
                        if "Student" in upload_type:
                            results = run_async(bulk_create_students(df, program_id, default_password))
                        elif "Teacher" in upload_type:
                            results = run_async(bulk_create_teachers(df, program_id, default_password))
                        else:
                            results = run_async(bulk_create_store_staff(df, default_password))
                    
                    # Show results
                    st.markdown("### Upload Results")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("✅ Successful", results["success"])
                    with col2:
                        st.metric("❌ Failed", results["failed"])
                    
                    if results["errors"]:
                        with st.expander(f"View {len(results['errors'])} Errors"):
                            for error in results["errors"]:
                                st.error(error)
                    
                    if results["success"] > 0:
                        st.balloons()
        
        except Exception as e:
            st.error(f"Error parsing file: {e}")
    
    # Download templates
    st.markdown("---")
    st.markdown("### Download Templates")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        template_df = pd.DataFrame({
            "email": ["student1@academy.edu", "student2@academy.edu"],
            "full_name": ["John Doe", "Jane Smith"],
            "password": ["", "custompass123"]
        })
        csv = template_df.to_csv(index=False)
        st.download_button(
            "📥 Student Template (CSV)",
            csv,
            "student_template.csv",
            "text/csv"
        )
    
    with col2:
        template_df = pd.DataFrame({
            "email": ["teacher1@academy.edu", "teacher2@academy.edu"],
            "full_name": ["Dr. John Doe", "Prof. Jane Smith"],
            "password": ["", ""]
        })
        csv = template_df.to_csv(index=False)
        st.download_button(
            "📥 Teacher Template (CSV)",
            csv,
            "teacher_template.csv",
            "text/csv"
        )
    
    with col3:
        template_df = pd.DataFrame({
            "email": ["store1@academy.edu", "store2@academy.edu"],
            "full_name": ["Store Staff 1", "Store Staff 2"],
            "password": ["", ""]
        })
        csv = template_df.to_csv(index=False)
        st.download_button(
            "📥 Store Staff Template (CSV)",
            csv,
            "store_template.csv",
            "text/csv"
        )
