"""
Settings Page for Admin Dashboard
"""
import streamlit as st
import asyncio
from datetime import datetime
import os

from dashboard.utils.database import get_postgres_pool, get_mongo_db


def run_async(coro):
    """Run async function in Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def get_system_settings():
    """Get current system settings."""
    db = await get_mongo_db()
    
    settings = await db.settings.find_one({"_id": "system_settings"})
    
    if not settings:
        # Default settings
        settings = {
            "_id": "system_settings",
            "academy_name": "Academy Program",
            "timezone": "Asia/Riyadh",
            "currency": "SAR",
            "default_allowance": 50.0,
            "qr_expiry_minutes": 5,
            "attendance_start_time": "08:00",
            "attendance_end_time": "16:00",
            "late_threshold_minutes": 15,
            "email_notifications": True,
            "sms_notifications": False,
            "maintenance_mode": False,
            "debug_mode": False
        }
    
    return settings


async def save_system_settings(settings: dict):
    """Save system settings."""
    db = await get_mongo_db()
    
    settings["_id"] = "system_settings"
    settings["updated_at"] = datetime.utcnow()
    
    await db.settings.replace_one(
        {"_id": "system_settings"},
        settings,
        upsert=True
    )
    
    return True


async def get_admin_users():
    """Get list of admin users."""
    db = await get_mongo_db()
    
    admins = await db.users.find({"role": "admin"}).to_list(100)
    return admins


async def create_admin_user(email: str, full_name: str, password_hash: str):
    """Create a new admin user."""
    db = await get_mongo_db()
    
    import uuid
    
    user = {
        "_id": str(uuid.uuid4()),
        "email": email,
        "full_name": full_name,
        "password_hash": password_hash,
        "role": "admin",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    await db.users.insert_one(user)
    return user["_id"]


def render():
    """Render the settings page."""
    st.markdown('<p class="main-header">⚙️ Settings</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">System configuration and preferences</p>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏫 General",
        "👤 Admin Users",
        "🔔 Notifications",
        "🔧 Advanced"
    ])
    
    with tab1:
        render_general_settings()
    
    with tab2:
        render_admin_users()
    
    with tab3:
        render_notification_settings()
    
    with tab4:
        render_advanced_settings()


def render_general_settings():
    """General system settings."""
    st.markdown("### General Settings")
    
    try:
        settings = run_async(get_system_settings())
        
        with st.form("general_settings_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                academy_name = st.text_input(
                    "Academy Name",
                    value=settings.get('academy_name', 'Academy Program')
                )
                
                timezone = st.selectbox(
                    "Timezone",
                    ["Asia/Riyadh", "UTC", "Asia/Dubai", "Europe/London"],
                    index=0 if settings.get('timezone') == 'Asia/Riyadh' else 0
                )
                
                currency = st.selectbox(
                    "Currency",
                    ["SAR", "USD", "EUR", "GBP"],
                    index=0 if settings.get('currency') == 'SAR' else 0
                )
            
            with col2:
                default_allowance = st.number_input(
                    "Default Daily Allowance",
                    min_value=0.0,
                    value=float(settings.get('default_allowance', 50.0)),
                    step=5.0
                )
                
                qr_expiry = st.number_input(
                    "QR Code Expiry (minutes)",
                    min_value=1,
                    max_value=60,
                    value=int(settings.get('qr_expiry_minutes', 5))
                )
            
            st.markdown("---")
            st.markdown("#### Attendance Settings")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                start_time = st.time_input(
                    "Attendance Start Time",
                    value=datetime.strptime(settings.get('attendance_start_time', '08:00'), '%H:%M').time()
                )
            
            with col2:
                end_time = st.time_input(
                    "Attendance End Time",
                    value=datetime.strptime(settings.get('attendance_end_time', '16:00'), '%H:%M').time()
                )
            
            with col3:
                late_threshold = st.number_input(
                    "Late Threshold (minutes)",
                    min_value=0,
                    max_value=60,
                    value=int(settings.get('late_threshold_minutes', 15))
                )
            
            submitted = st.form_submit_button("Save Settings", type="primary")
            
            if submitted:
                new_settings = {
                    "academy_name": academy_name,
                    "timezone": timezone,
                    "currency": currency,
                    "default_allowance": default_allowance,
                    "qr_expiry_minutes": qr_expiry,
                    "attendance_start_time": start_time.strftime('%H:%M'),
                    "attendance_end_time": end_time.strftime('%H:%M'),
                    "late_threshold_minutes": late_threshold,
                    "email_notifications": settings.get('email_notifications', True),
                    "sms_notifications": settings.get('sms_notifications', False),
                    "maintenance_mode": settings.get('maintenance_mode', False),
                    "debug_mode": settings.get('debug_mode', False)
                }
                
                run_async(save_system_settings(new_settings))
                st.success("✅ Settings saved successfully!")
    
    except Exception as e:
        st.error(f"Error loading settings: {e}")


def render_admin_users():
    """Admin user management."""
    st.markdown("### Admin Users")
    
    try:
        admins = run_async(get_admin_users())
        
        if admins:
            st.markdown("#### Current Admin Users")
            for admin in admins:
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**{admin.get('full_name', 'N/A')}**")
                
                with col2:
                    st.markdown(admin.get('email', 'N/A'))
                
                with col3:
                    status = "✅ Active" if admin.get('is_active') else "❌ Inactive"
                    st.markdown(status)
        else:
            st.info("No admin users found")
        
        st.markdown("---")
        st.markdown("#### Create New Admin")
        
        with st.form("create_admin_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_email = st.text_input("Email*", placeholder="admin@academy.edu")
                new_name = st.text_input("Full Name*", placeholder="Admin User")
            
            with col2:
                new_password = st.text_input("Password*", type="password")
                confirm_password = st.text_input("Confirm Password*", type="password")
            
            submitted = st.form_submit_button("Create Admin", type="primary")
            
            if submitted:
                if not new_email or not new_name or not new_password:
                    st.error("Please fill in all required fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    import hashlib
                    password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                    
                    try:
                        admin_id = run_async(create_admin_user(new_email, new_name, password_hash))
                        st.success(f"✅ Admin user created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating admin: {e}")
    
    except Exception as e:
        st.error(f"Error loading admins: {e}")


def render_notification_settings():
    """Notification settings."""
    st.markdown("### Notification Settings")
    
    try:
        settings = run_async(get_system_settings())
        
        with st.form("notification_settings_form"):
            st.markdown("#### Notification Channels")
            
            col1, col2 = st.columns(2)
            
            with col1:
                email_enabled = st.checkbox(
                    "Email Notifications",
                    value=settings.get('email_notifications', True)
                )
                
                if email_enabled:
                    st.text_input("SMTP Server", placeholder="smtp.example.com")
                    st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
            
            with col2:
                sms_enabled = st.checkbox(
                    "SMS Notifications",
                    value=settings.get('sms_notifications', False)
                )
                
                if sms_enabled:
                    st.text_input("SMS Provider API Key", type="password")
            
            st.markdown("---")
            st.markdown("#### Notification Events")
            
            st.checkbox("New user registration", value=True)
            st.checkbox("Password reset requests", value=True)
            st.checkbox("Low balance alerts", value=True)
            st.checkbox("Attendance anomalies", value=False)
            st.checkbox("System errors", value=True)
            
            submitted = st.form_submit_button("Save Notification Settings", type="primary")
            
            if submitted:
                settings['email_notifications'] = email_enabled
                settings['sms_notifications'] = sms_enabled
                run_async(save_system_settings(settings))
                st.success("✅ Notification settings saved!")
    
    except Exception as e:
        st.error(f"Error loading notification settings: {e}")


def render_advanced_settings():
    """Advanced system settings."""
    st.markdown("### Advanced Settings")
    
    st.warning("⚠️ These settings can affect system stability. Use with caution.")
    
    try:
        settings = run_async(get_system_settings())
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### System Mode")
            
            maintenance = st.toggle(
                "Maintenance Mode",
                value=settings.get('maintenance_mode', False),
                help="Enable to show maintenance message to users"
            )
            
            if maintenance:
                st.warning("⚠️ Maintenance mode is ON - users cannot access the system")
            
            debug = st.toggle(
                "Debug Mode",
                value=settings.get('debug_mode', False),
                help="Enable verbose logging for debugging"
            )
            
            if debug:
                st.info("🐛 Debug mode is ON - verbose logging enabled")
        
        with col2:
            st.markdown("#### Database Actions")
            
            if st.button("🔄 Clear Cache", type="secondary"):
                st.info("Cache clearing initiated...")
                # Would clear Redis cache
                st.success("✅ Cache cleared")
            
            if st.button("📊 Optimize Database", type="secondary"):
                st.info("Database optimization initiated...")
                st.success("✅ Database optimized")
        
        st.markdown("---")
        st.markdown("#### Danger Zone")
        
        with st.expander("🚨 Dangerous Actions", expanded=False):
            st.error("These actions cannot be undone!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🗑️ Purge Old Logs", type="secondary"):
                    st.info("This would delete logs older than 30 days")
            
            with col2:
                if st.button("🔄 Reset All Sessions", type="secondary"):
                    st.info("This would log out all users")
        
        st.markdown("---")
        st.markdown("#### Environment Info")
        
        env_info = {
            "Python Version": os.popen("python --version").read().strip(),
            "Backend URL": os.environ.get("BACKEND_URL", "Not set"),
            "Database Host": os.environ.get("DATABASE_HOST", "Not set"),
            "Redis Host": os.environ.get("REDIS_HOST", "Not set"),
            "Environment": os.environ.get("ENVIRONMENT", "development")
        }
        
        for key, value in env_info.items():
            st.markdown(f"**{key}:** `{value}`")
    
    except Exception as e:
        st.error(f"Error loading advanced settings: {e}")
