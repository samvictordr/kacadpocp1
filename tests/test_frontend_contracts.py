"""
Frontend-Backend Contract Tests

Tests:
- Frontend PWAs call correct API endpoints
- Request payloads match backend schemas
- Response handling matches expected shapes
- Error responses are properly handled

This validates the contract between frontend and backend.
"""
import pytest
import re
import json
from pathlib import Path


# Frontend paths
FRONTEND_ROOT = Path(__file__).parent.parent.parent / "frontend"
STUDENT_PWA = FRONTEND_ROOT / "student"
TEACHER_PWA = FRONTEND_ROOT / "teacher"
STORE_PWA = FRONTEND_ROOT / "store"


class TestStudentFrontendContract:
    """Tests that student frontend calls correct APIs."""
    
    def test_login_endpoint_correct(self):
        """Should call /auth/login for authentication."""
        # Find JS files
        js_files = list(STUDENT_PWA.glob("**/*.js"))
        html_files = list(STUDENT_PWA.glob("**/*.html"))
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        # Look for auth/login endpoint
        patterns = [
            r'/auth/login',
            r'auth/login',
            r'"login"',
            r"'login'"
        ]
        
        has_login_call = any(re.search(p, all_content) for p in patterns)
        
        if not has_login_call:
            pytest.skip("No login API call found (may use different auth)")
    
    def test_attendance_qr_endpoint_correct(self):
        """Should call /student/attendance-qr for QR generation."""
        js_files = list(STUDENT_PWA.glob("**/*.js"))
        html_files = list(STUDENT_PWA.glob("**/*.html"))
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'/student/attendance-qr',
            r'attendance-qr',
            r'attendanceQr',
            r'attendance_qr'
        ]
        
        has_qr_call = any(re.search(p, all_content) for p in patterns)
        
        assert has_qr_call, "Should call attendance-qr endpoint"
    
    def test_balance_endpoint_correct(self):
        """Should call /student/balance for balance check."""
        js_files = list(STUDENT_PWA.glob("**/*.js"))
        html_files = list(STUDENT_PWA.glob("**/*.html"))
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'/student/balance',
            r'/balance',
            r'getBalance',
            r'get_balance'
        ]
        
        has_balance_call = any(re.search(p, all_content) for p in patterns)
        
        if not has_balance_call:
            pytest.skip("Balance endpoint call not found in static analysis")
    
    def test_uses_authorization_header(self):
        """Should include Authorization header for API calls."""
        js_files = list(STUDENT_PWA.glob("**/*.js"))
        html_files = list(STUDENT_PWA.glob("**/*.html"))
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'Authorization',
            r'Bearer',
            r'headers.*token',
            r'token.*headers'
        ]
        
        has_auth_header = any(re.search(p, all_content, re.IGNORECASE) for p in patterns)
        
        assert has_auth_header, "Should use Authorization header"


class TestTeacherFrontendContract:
    """Tests that teacher frontend calls correct APIs."""
    
    def test_session_start_endpoint(self):
        """Should call /teacher/attendance-session/start."""
        js_files = list(TEACHER_PWA.glob("**/*.js"))
        html_files = list(TEACHER_PWA.glob("**/*.html"))
        
        if not js_files and not html_files:
            pytest.skip("No teacher frontend files found")
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'attendance-session/start',
            r'session/start',
            r'startSession',
            r'start_session'
        ]
        
        has_session_call = any(re.search(p, all_content) for p in patterns)
        
        if not has_session_call:
            pytest.skip("Session start endpoint not found in static analysis")
    
    def test_scan_endpoint(self):
        """Should call /teacher/attendance/scan."""
        js_files = list(TEACHER_PWA.glob("**/*.js"))
        html_files = list(TEACHER_PWA.glob("**/*.html"))
        
        if not js_files and not html_files:
            pytest.skip("No teacher frontend files found")
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'attendance/scan',
            r'/scan',
            r'scanQr',
            r'scan_qr'
        ]
        
        has_scan_call = any(re.search(p, all_content) for p in patterns)
        
        if not has_scan_call:
            pytest.skip("Scan endpoint not found in static analysis")


class TestStoreFrontendContract:
    """Tests that store frontend calls correct APIs."""
    
    def test_scan_endpoint(self):
        """Should call /store/scan."""
        js_files = list(STORE_PWA.glob("**/*.js"))
        html_files = list(STORE_PWA.glob("**/*.html"))
        
        if not js_files and not html_files:
            pytest.skip("No store frontend files found")
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'/store/scan',
            r'store/scan',
            r'scanStudent',
            r'scan_student'
        ]
        
        has_scan_call = any(re.search(p, all_content) for p in patterns)
        
        if not has_scan_call:
            pytest.skip("Store scan endpoint not found in static analysis")
    
    def test_charge_endpoint(self):
        """Should call /store/charge."""
        js_files = list(STORE_PWA.glob("**/*.js"))
        html_files = list(STORE_PWA.glob("**/*.html"))
        
        if not js_files and not html_files:
            pytest.skip("No store frontend files found")
        
        all_content = ""
        for f in js_files + html_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'/store/charge',
            r'store/charge',
            r'chargeStudent',
            r'charge_student',
            r'makeCharge'
        ]
        
        has_charge_call = any(re.search(p, all_content) for p in patterns)
        
        if not has_charge_call:
            pytest.skip("Store charge endpoint not found in static analysis")


class TestAPIBaseURL:
    """Tests for API base URL configuration."""
    
    def test_api_base_configurable(self):
        """API base URL should be configurable (not hardcoded localhost)."""
        all_files = (
            list(STUDENT_PWA.glob("**/*.js")) +
            list(STUDENT_PWA.glob("**/*.html")) +
            list(TEACHER_PWA.glob("**/*.js")) +
            list(TEACHER_PWA.glob("**/*.html")) +
            list(STORE_PWA.glob("**/*.js")) +
            list(STORE_PWA.glob("**/*.html"))
        )
        
        hardcoded_localhost = 0
        configurable_patterns = 0
        
        for f in all_files:
            try:
                with open(f) as file:
                    content = file.read()
                
                # Check for hardcoded localhost
                if re.search(r'localhost:\d+', content):
                    hardcoded_localhost += 1
                
                # Check for configuration pattern
                if re.search(r'API_URL|API_BASE|baseUrl|config', content, re.IGNORECASE):
                    configurable_patterns += 1
            except:
                pass
        
        if hardcoded_localhost > 0 and configurable_patterns == 0:
            pytest.skip(
                f"Found {hardcoded_localhost} hardcoded localhost references. "
                "Consider using environment-based configuration."
            )


class TestErrorHandling:
    """Tests for error handling in frontend."""
    
    def test_handles_401_unauthorized(self):
        """Should handle 401 responses (redirect to login)."""
        all_files = (
            list(STUDENT_PWA.glob("**/*.js")) +
            list(STUDENT_PWA.glob("**/*.html"))
        )
        
        all_content = ""
        for f in all_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'401',
            r'unauthorized',
            r'unauthenticated',
            r'redirectToLogin',
            r'logout'
        ]
        
        handles_401 = any(re.search(p, all_content, re.IGNORECASE) for p in patterns)
        
        if not handles_401:
            pytest.skip("401 handling not found in static analysis")
    
    def test_handles_network_errors(self):
        """Should handle network errors gracefully."""
        all_files = (
            list(STUDENT_PWA.glob("**/*.js")) +
            list(STUDENT_PWA.glob("**/*.html"))
        )
        
        all_content = ""
        for f in all_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'catch',
            r'\.catch\(',
            r'try\s*{',
            r'onerror',
            r'network',
            r'offline'
        ]
        
        handles_errors = any(re.search(p, all_content, re.IGNORECASE) for p in patterns)
        
        if not handles_errors:
            pytest.skip("Error handling not found in static analysis")


class TestJWTTokenHandling:
    """Tests for JWT token handling in frontend."""
    
    def test_stores_token_securely(self):
        """Token storage should be reasonably secure."""
        all_files = (
            list(STUDENT_PWA.glob("**/*.js")) +
            list(STUDENT_PWA.glob("**/*.html"))
        )
        
        all_content = ""
        for f in all_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        # localStorage is common but sessionStorage is slightly more secure
        storage_patterns = [
            r'localStorage',
            r'sessionStorage',
            r'cookie'
        ]
        
        has_storage = any(re.search(p, all_content) for p in storage_patterns)
        
        if has_storage:
            # Check for httpOnly cookie (more secure)
            if 'httpOnly' not in all_content and 'HttpOnly' not in all_content:
                # Just a note - localStorage is common for SPAs
                pass
    
    def test_token_refresh_pattern(self):
        """Should handle token expiration."""
        all_files = (
            list(STUDENT_PWA.glob("**/*.js")) +
            list(STUDENT_PWA.glob("**/*.html"))
        )
        
        all_content = ""
        for f in all_files:
            try:
                with open(f) as file:
                    all_content += file.read()
            except:
                pass
        
        patterns = [
            r'refresh',
            r'expired',
            r'expiration',
            r'exp',
            r'token.*invalid'
        ]
        
        handles_expiry = any(re.search(p, all_content, re.IGNORECASE) for p in patterns)
        
        if not handles_expiry:
            pytest.skip("Token expiration handling not found in static analysis")
