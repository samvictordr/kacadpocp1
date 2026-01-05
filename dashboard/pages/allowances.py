"""
Allowances Management Page
"""
import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime, date
import uuid

from dashboard.utils.database import (
    get_students_from_postgres, get_programs_from_postgres,
    get_daily_allowances, get_postgres_pool
)


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def set_daily_allowance(student_id: str, allowance_date: date, base_amount: float, bonus_amount: float = 0):
    """Set daily allowance for a student."""
    pool = await get_postgres_pool()
    
    total = base_amount + bonus_amount
    allowance_id = str(uuid.uuid4())
    
    async with pool.acquire() as conn:
        # Check if allowance exists for this day
        existing = await conn.fetchval("""
            SELECT allowance_id FROM daily_allowances 
            WHERE student_id = $1 AND date = $2
        """, student_id, allowance_date)
        
        if existing:
            # Update existing
            await conn.execute("""
                UPDATE daily_allowances 
                SET base_amount = $1, bonus_amount = $2, total_amount = $3
                WHERE student_id = $4 AND date = $5
            """, base_amount, bonus_amount, total, student_id, allowance_date)
            return True, "Allowance updated"
        else:
            # Insert new
            await conn.execute("""
                INSERT INTO daily_allowances (allowance_id, student_id, date, base_amount, bonus_amount, total_amount)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, allowance_id, student_id, allowance_date, base_amount, bonus_amount, total)
            return True, "Allowance created"


async def bulk_set_allowances(program_id: str, allowance_date: date, base_amount: float, bonus_amount: float = 0):
    """Set allowances for all students in a program."""
    pool = await get_postgres_pool()
    
    async with pool.acquire() as conn:
        # Get all students in program
        students = await conn.fetch("""
            SELECT student_id FROM students WHERE program_id = $1 AND is_active = true
        """, program_id)
        
        count = 0
        for student in students:
            await set_daily_allowance(student["student_id"], allowance_date, base_amount, bonus_amount)
            count += 1
        
        return count


async def update_program_default_allowance(program_id: str, amount: float):
    """Update the default daily allowance for a program."""
    pool = await get_postgres_pool()
    
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE programs SET default_daily_allowance = $1 WHERE program_id = $2
        """, amount, program_id)
    
    return True


def render():
    """Render the allowances page."""
    st.markdown('<p class="main-header">💰 Allowances</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Manage daily allowances for students</p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 View Allowances", 
        "➕ Set Individual", 
        "📦 Bulk Set by Program",
        "⚙️ Program Defaults"
    ])
    
    with tab1:
        render_view_allowances()
    
    with tab2:
        render_set_individual()
    
    with tab3:
        render_bulk_set()
    
    with tab4:
        render_program_defaults()


def render_view_allowances():
    """View current allowances."""
    st.markdown("### Current Allowances")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        filter_date = st.date_input("Filter by Date", value=date.today())
    
    try:
        allowances = run_async(get_daily_allowances(str(filter_date)))
        
        if allowances:
            df = pd.DataFrame(allowances)
            
            # Format amounts
            for col in ["base_amount", "bonus_amount", "total_amount"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"{float(x):.2f} SAR")
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(f"Total: {len(allowances)} allowances for {filter_date}")
        else:
            st.info(f"No allowances found for {filter_date}")
    
    except Exception as e:
        st.error(f"Error loading allowances: {e}")


def render_set_individual():
    """Set allowance for individual student."""
    st.markdown("### Set Individual Allowance")
    
    try:
        students = run_async(get_students_from_postgres())
        student_options = {f"{s['full_name']} ({s['student_id'][:8]}...)": s['student_id'] for s in students}
    except:
        student_options = {}
    
    if not student_options:
        st.warning("No students found. Please add students first.")
        return
    
    with st.form("set_allowance_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            student = st.selectbox("Select Student", list(student_options.keys()))
            allowance_date = st.date_input("Date", value=date.today())
        
        with col2:
            base_amount = st.number_input("Base Amount (SAR)", min_value=0.0, value=50.0, step=5.0)
            bonus_amount = st.number_input("Bonus Amount (SAR)", min_value=0.0, value=0.0, step=5.0)
        
        st.markdown(f"**Total Allowance: {base_amount + bonus_amount:.2f} SAR**")
        
        submitted = st.form_submit_button("Set Allowance", type="primary")
        
        if submitted:
            student_id = student_options[student]
            success, msg = run_async(set_daily_allowance(student_id, allowance_date, base_amount, bonus_amount))
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")


def render_bulk_set():
    """Bulk set allowances by program."""
    st.markdown("### Bulk Set by Program")
    st.info("Set the same allowance for all students in a program for a specific date.")
    
    try:
        programs = run_async(get_programs_from_postgres())
        program_options = {p["name"]: p["program_id"] for p in programs}
    except:
        program_options = {}
    
    if not program_options:
        st.warning("No programs found. Please add programs first.")
        return
    
    with st.form("bulk_allowance_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            program = st.selectbox("Select Program", list(program_options.keys()))
            allowance_date = st.date_input("Date", value=date.today())
        
        with col2:
            base_amount = st.number_input("Base Amount (SAR)", min_value=0.0, value=50.0, step=5.0)
            bonus_amount = st.number_input("Bonus Amount (SAR)", min_value=0.0, value=0.0, step=5.0)
        
        st.warning("⚠️ This will set allowances for ALL active students in the selected program.")
        
        submitted = st.form_submit_button("Set Bulk Allowances", type="primary")
        
        if submitted:
            program_id = program_options[program]
            with st.spinner("Setting allowances..."):
                count = run_async(bulk_set_allowances(program_id, allowance_date, base_amount, bonus_amount))
            st.success(f"✅ Set allowances for {count} students")


def render_program_defaults():
    """Manage program default allowances."""
    st.markdown("### Program Default Allowances")
    st.info("Set the default daily allowance for each program. This will be used when generating daily allowances.")
    
    try:
        programs = run_async(get_programs_from_postgres())
        
        if not programs:
            st.warning("No programs found.")
            return
        
        for program in programs:
            with st.expander(f"📚 {program['name']}", expanded=False):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**Cost Center:** {program.get('cost_center', 'N/A')}")
                    st.markdown(f"**Active:** {'Yes' if program.get('is_active') else 'No'}")
                
                with col2:
                    current = float(program.get('default_daily_allowance', 0))
                    st.markdown(f"**Current Default:** {current:.2f} SAR")
                
                with col3:
                    new_amount = st.number_input(
                        "New Amount",
                        min_value=0.0,
                        value=current,
                        step=5.0,
                        key=f"prog_{program['program_id']}"
                    )
                    if st.button("Update", key=f"btn_{program['program_id']}"):
                        run_async(update_program_default_allowance(program['program_id'], new_amount))
                        st.success("Updated!")
                        st.rerun()
    
    except Exception as e:
        st.error(f"Error loading programs: {e}")
