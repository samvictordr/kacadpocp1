"""
Authentication utilities for the admin dashboard.
"""
import streamlit as st
import hashlib
import os
from datetime import datetime, timedelta

# Admin credentials (in production, use environment variables)
ADMIN_USERS = {
    "admin@academy.edu": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "name": "System Admin",
        "role": "super_admin"
    }
}


def verify_password(email: str, password: str) -> bool:
    """Verify admin credentials."""
    if email not in ADMIN_USERS:
        return False
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return ADMIN_USERS[email]["password_hash"] == password_hash


def check_admin_auth() -> bool:
    """Check if user is authenticated."""
    return st.session_state.get('authenticated', False)


def show_login_page():
    """Display the login page."""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("")
        st.markdown("")
        st.markdown('<p class="main-header">🎓 Academy Admin</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Sign in to access the dashboard</p>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="admin@academy.edu")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col_a, col_b = st.columns([1, 1])
            with col_b:
                submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            
            if submitted:
                if verify_password(email, password):
                    st.session_state.authenticated = True
                    st.session_state.admin_user = ADMIN_USERS[email]["name"]
                    st.session_state.admin_email = email
                    st.session_state.login_time = datetime.now()
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")
        
        st.markdown("---")
        st.markdown(
            "<p style='text-align: center; color: #888; font-size: 0.85rem;'>"
            "Academy Platform Admin Dashboard v1.0<br>"
            "For authorized personnel only."
            "</p>",
            unsafe_allow_html=True
        )


def require_auth(func):
    """Decorator to require authentication for a page."""
    def wrapper(*args, **kwargs):
        if not check_admin_auth():
            show_login_page()
            return
        return func(*args, **kwargs)
    return wrapper
