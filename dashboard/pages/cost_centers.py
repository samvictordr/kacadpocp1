"""
Cost Centers Management Page
"""
import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
import uuid

from dashboard.utils.database import get_programs_from_postgres, get_postgres_pool


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def get_cost_centers():
    """Get all cost centers with aggregated data."""
    pool = await get_postgres_pool()
    
    async with pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT 
                p.program_id,
                p.name,
                p.cost_center,
                p.default_daily_allowance,
                p.is_active,
                p.created_at,
                COUNT(DISTINCT s.student_id) as student_count,
                COUNT(DISTINCT t.teacher_id) as teacher_count
            FROM programs p
            LEFT JOIN students s ON p.program_id = s.program_id AND s.is_active = true
            LEFT JOIN teachers t ON p.program_id = t.program_id AND t.is_active = true
            GROUP BY p.program_id
            ORDER BY p.name
        """)
        
        return [dict(r) for r in results]


async def create_program(name: str, cost_center: str, default_allowance: float):
    """Create a new program/cost center."""
    pool = await get_postgres_pool()
    program_id = str(uuid.uuid4())
    
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO programs (program_id, name, cost_center, default_daily_allowance, is_active)
            VALUES ($1, $2, $3, $4, true)
        """, program_id, name, cost_center, default_allowance)
    
    return program_id


async def update_program(program_id: str, name: str, cost_center: str, default_allowance: float, is_active: bool):
    """Update an existing program."""
    pool = await get_postgres_pool()
    
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE programs 
            SET name = $1, cost_center = $2, default_daily_allowance = $3, is_active = $4
            WHERE program_id = $5
        """, name, cost_center, default_allowance, is_active, program_id)
    
    return True


async def delete_program(program_id: str):
    """Delete a program (only if no students/teachers)."""
    pool = await get_postgres_pool()
    
    async with pool.acquire() as conn:
        # Check for students
        student_count = await conn.fetchval(
            "SELECT COUNT(*) FROM students WHERE program_id = $1", program_id
        )
        teacher_count = await conn.fetchval(
            "SELECT COUNT(*) FROM teachers WHERE program_id = $1", program_id
        )
        
        if student_count > 0 or teacher_count > 0:
            return False, f"Cannot delete: {student_count} students and {teacher_count} teachers assigned"
        
        await conn.execute("DELETE FROM programs WHERE program_id = $1", program_id)
        return True, "Program deleted"


async def get_cost_center_spending(program_id: str, start_date: str, end_date: str):
    """Get spending summary for a cost center."""
    pool = await get_postgres_pool()
    
    async with pool.acquire() as conn:
        # Total allowances disbursed
        allowance_total = await conn.fetchval("""
            SELECT COALESCE(SUM(da.total_amount), 0)
            FROM daily_allowances da
            JOIN students s ON da.student_id = s.student_id
            WHERE s.program_id = $1 AND da.date BETWEEN $2 AND $3
        """, program_id, start_date, end_date)
        
        # Total store transactions
        transaction_total = await conn.fetchval("""
            SELECT COALESCE(SUM(st.total_amount), 0)
            FROM store_transactions st
            JOIN students s ON st.student_id = s.student_id
            WHERE s.program_id = $1 AND DATE(st.transaction_time) BETWEEN $2 AND $3
        """, program_id, start_date, end_date)
        
        return {
            "allowances_disbursed": float(allowance_total or 0),
            "store_spending": float(transaction_total or 0)
        }


def render():
    """Render the cost centers page."""
    st.markdown('<p class="main-header">🏢 Cost Centers</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Manage programs and cost centers</p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 All Cost Centers",
        "➕ Create New",
        "📊 Spending Reports",
        "⚙️ Manage"
    ])
    
    with tab1:
        render_all_cost_centers()
    
    with tab2:
        render_create_program()
    
    with tab3:
        render_spending_reports()
    
    with tab4:
        render_manage_programs()


def render_all_cost_centers():
    """View all cost centers."""
    st.markdown("### All Cost Centers")
    
    try:
        cost_centers = run_async(get_cost_centers())
        
        if not cost_centers:
            st.info("No cost centers found. Create one to get started.")
            return
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Programs", len(cost_centers))
        
        with col2:
            active = sum(1 for c in cost_centers if c.get('is_active'))
            st.metric("Active", active)
        
        with col3:
            total_students = sum(c.get('student_count', 0) for c in cost_centers)
            st.metric("Total Students", total_students)
        
        with col4:
            total_teachers = sum(c.get('teacher_count', 0) for c in cost_centers)
            st.metric("Total Teachers", total_teachers)
        
        st.markdown("---")
        
        # Table view
        df = pd.DataFrame(cost_centers)
        df = df.rename(columns={
            'program_id': 'ID',
            'name': 'Program Name',
            'cost_center': 'Cost Center Code',
            'default_daily_allowance': 'Default Allowance',
            'is_active': 'Active',
            'student_count': 'Students',
            'teacher_count': 'Teachers'
        })
        
        # Format allowance
        df['Default Allowance'] = df['Default Allowance'].apply(lambda x: f"{float(x):.2f} SAR")
        
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    except Exception as e:
        st.error(f"Error loading cost centers: {e}")


def render_create_program():
    """Create a new program/cost center."""
    st.markdown("### Create New Program")
    
    with st.form("create_program_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Program Name*", placeholder="e.g., Computer Science 2024")
            default_allowance = st.number_input("Default Daily Allowance (SAR)", min_value=0.0, value=50.0, step=5.0)
        
        with col2:
            cost_center = st.text_input("Cost Center Code*", placeholder="e.g., CC-CS-2024")
        
        st.markdown("*Required fields")
        
        submitted = st.form_submit_button("Create Program", type="primary")
        
        if submitted:
            if not name or not cost_center:
                st.error("Please fill in all required fields")
            else:
                try:
                    program_id = run_async(create_program(name, cost_center, default_allowance))
                    st.success(f"✅ Program created with ID: {program_id[:8]}...")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error creating program: {e}")


def render_spending_reports():
    """Spending reports by cost center."""
    st.markdown("### Spending Reports")
    
    try:
        programs = run_async(get_programs_from_postgres())
        program_options = {p["name"]: p["program_id"] for p in programs}
    except:
        program_options = {}
    
    if not program_options:
        st.warning("No programs found.")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_program = st.selectbox("Select Program", list(program_options.keys()))
    
    with col2:
        from datetime import date, timedelta
        start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30))
    
    with col3:
        end_date = st.date_input("End Date", value=date.today())
    
    if st.button("Generate Report", type="primary"):
        program_id = program_options[selected_program]
        
        try:
            spending = run_async(get_cost_center_spending(program_id, str(start_date), str(end_date)))
            
            st.markdown("---")
            st.markdown(f"### Report for {selected_program}")
            st.markdown(f"**Period:** {start_date} to {end_date}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Allowances Disbursed", f"{spending['allowances_disbursed']:.2f} SAR")
            
            with col2:
                st.metric("Store Spending", f"{spending['store_spending']:.2f} SAR")
            
            with col3:
                remaining = spending['allowances_disbursed'] - spending['store_spending']
                st.metric("Remaining Balance", f"{remaining:.2f} SAR")
            
            # Utilization chart
            if spending['allowances_disbursed'] > 0:
                utilization = (spending['store_spending'] / spending['allowances_disbursed']) * 100
                st.progress(min(utilization / 100, 1.0), text=f"Budget Utilization: {utilization:.1f}%")
        
        except Exception as e:
            st.error(f"Error generating report: {e}")


def render_manage_programs():
    """Manage existing programs."""
    st.markdown("### Manage Programs")
    
    try:
        cost_centers = run_async(get_cost_centers())
        
        if not cost_centers:
            st.info("No programs to manage.")
            return
        
        for program in cost_centers:
            with st.expander(f"📚 {program['name']} ({program['cost_center']})", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    with st.form(f"edit_{program['program_id']}"):
                        new_name = st.text_input("Program Name", value=program['name'])
                        new_cost_center = st.text_input("Cost Center Code", value=program['cost_center'])
                        new_allowance = st.number_input(
                            "Default Allowance (SAR)", 
                            min_value=0.0, 
                            value=float(program['default_daily_allowance']),
                            step=5.0
                        )
                        is_active = st.checkbox("Active", value=program['is_active'])
                        
                        if st.form_submit_button("Update"):
                            run_async(update_program(
                                program['program_id'], 
                                new_name, 
                                new_cost_center, 
                                new_allowance, 
                                is_active
                            ))
                            st.success("Updated!")
                            st.rerun()
                
                with col2:
                    st.markdown("**Statistics:**")
                    st.markdown(f"- Students: {program['student_count']}")
                    st.markdown(f"- Teachers: {program['teacher_count']}")
                    
                    st.markdown("---")
                    
                    if program['student_count'] == 0 and program['teacher_count'] == 0:
                        if st.button("🗑️ Delete", key=f"del_{program['program_id']}", type="secondary"):
                            success, msg = run_async(delete_program(program['program_id']))
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.info("Cannot delete: has assigned users")
    
    except Exception as e:
        st.error(f"Error loading programs: {e}")
