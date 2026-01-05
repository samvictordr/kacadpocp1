"""
Home / Dashboard Overview Page
"""
import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime, timedelta

from dashboard.utils.database import (
    get_all_health_status, get_telemetry_stats,
    get_transaction_trends, get_attendance_trends
)


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def render():
    """Render the home page."""
    st.markdown('<p class="main-header">🏠 Dashboard Overview</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Welcome to the Academy Admin Dashboard</p>', unsafe_allow_html=True)
    
    # Quick Stats Row
    st.markdown("### 📊 Quick Stats")
    
    try:
        stats = run_async(get_telemetry_stats())
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="👨‍🎓 Active Students",
                value=stats.get("total_students", 0)
            )
        
        with col2:
            st.metric(
                label="👨‍🏫 Active Teachers",
                value=stats.get("total_teachers", 0)
            )
        
        with col3:
            st.metric(
                label="📚 Programs",
                value=stats.get("total_programs", 0)
            )
        
        with col4:
            st.metric(
                label="💳 Transactions Today",
                value=stats.get("transactions_today", 0)
            )
        
        with col5:
            amount = float(stats.get("transaction_amount_today", 0))
            st.metric(
                label="💰 Sales Today (SAR)",
                value=f"{amount:,.2f}"
            )
        
    except Exception as e:
        st.error(f"Error loading stats: {e}")
    
    st.markdown("---")
    
    # Service Health
    st.markdown("### 🏥 Service Health")
    
    try:
        health = run_async(get_all_health_status())
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            overall = health.get("overall", "unknown")
            if overall == "healthy":
                st.success("✅ **Overall: Healthy**")
            else:
                st.warning("⚠️ **Overall: Degraded**")
        
        services = health.get("services", {})
        
        with col2:
            pg = services.get("postgres", {})
            if pg.get("connected"):
                st.success(f"✅ **PostgreSQL**\n\n{pg.get('version', 'Connected')[:30]}")
            else:
                st.error(f"❌ **PostgreSQL**\n\n{pg.get('error', 'Disconnected')[:50]}")
        
        with col3:
            mongo = services.get("mongodb", {})
            if mongo.get("connected"):
                st.success(f"✅ **MongoDB**\n\nv{mongo.get('version', 'Connected')}")
            else:
                st.error(f"❌ **MongoDB**\n\n{mongo.get('error', 'Disconnected')[:50]}")
        
        with col4:
            redis_health = services.get("redis", {})
            if redis_health.get("connected"):
                st.success(f"✅ **Redis**\n\nv{redis_health.get('version', 'Connected')}")
            else:
                st.error(f"❌ **Redis**\n\n{redis_health.get('error', 'Disconnected')[:50]}")
    
    except Exception as e:
        st.error(f"Error checking health: {e}")
    
    st.markdown("---")
    
    # Charts Row
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💳 Transaction Trends (7 Days)")
        try:
            trends = run_async(get_transaction_trends(7))
            if trends:
                df = pd.DataFrame(trends)
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                st.line_chart(df[['count', 'total_amount']])
            else:
                st.info("No transaction data available")
        except Exception as e:
            st.error(f"Error loading trends: {e}")
    
    with col2:
        st.markdown("### 📋 Attendance Trends (7 Days)")
        try:
            trends = run_async(get_attendance_trends(7))
            if trends:
                df = pd.DataFrame(trends)
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                st.bar_chart(df['count'])
            else:
                st.info("No attendance data available")
        except Exception as e:
            st.error(f"Error loading trends: {e}")
    
    st.markdown("---")
    
    # Users by Role
    st.markdown("### 👥 Users by Role")
    try:
        if "users_by_role" in stats:
            roles = stats["users_by_role"]
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Students", roles.get("student", 0))
            with col2:
                st.metric("Teachers", roles.get("teacher", 0))
            with col3:
                st.metric("Store Staff", roles.get("store", 0))
            with col4:
                st.metric("Admins", roles.get("admin", 0))
    except Exception as e:
        st.error(f"Error loading user stats: {e}")
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<p style='text-align: center; color: #888;'>"
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        f"</p>",
        unsafe_allow_html=True
    )
