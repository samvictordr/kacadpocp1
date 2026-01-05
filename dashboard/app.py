"""
Academy Admin Dashboard - Main Entry Point
Streamlit-based admin interface for managing the Academy platform.
"""
import streamlit as st
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.utils.auth import check_admin_auth, show_login_page
from dashboard.utils.database import init_connections

# Page config
st.set_page_config(
    page_title="Academy Admin Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #FF9800;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px;
    }
    .success-box {
        background-color: #e8f5e9;
        border-left: 4px solid #4CAF50;
        padding: 16px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 16px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3e0;
        border-left: 4px solid #FF9800;
        padding: 16px;
        border-radius: 4px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main dashboard entry point."""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'admin_user' not in st.session_state:
        st.session_state.admin_user = None
    
    # Check authentication
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    # Sidebar navigation
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/graduation-cap.png", width=60)
        st.markdown("## 🎓 Academy Admin")
        st.markdown(f"**Logged in as:** {st.session_state.admin_user}")
        st.markdown("---")
        
        page = st.radio(
            "Navigation",
            ["🏠 Dashboard", "👥 User Management", "📤 Bulk Upload", "💰 Allowances", 
             "🏢 Cost Centers", "📊 Telemetry", "🔧 Settings"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.admin_user = None
            st.rerun()
    
    # Route to appropriate page
    if page == "🏠 Dashboard":
        from dashboard.pages import home
        home.render()
    elif page == "👥 User Management":
        from dashboard.pages import user_management
        user_management.render()
    elif page == "📤 Bulk Upload":
        from dashboard.pages import bulk_upload
        bulk_upload.render()
    elif page == "💰 Allowances":
        from dashboard.pages import allowances
        allowances.render()
    elif page == "🏢 Cost Centers":
        from dashboard.pages import cost_centers
        cost_centers.render()
    elif page == "📊 Telemetry":
        from dashboard.pages import telemetry
        telemetry.render()
    elif page == "🔧 Settings":
        from dashboard.pages import settings
        settings.render()


if __name__ == "__main__":
    main()
