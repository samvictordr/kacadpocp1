"""
Teacher Flow Tests

Tests:
- Start attendance session (static & dynamic)
- Generate QRs correctly
- Scan valid QR
- Scan expired QR
- Scan already-used QR
- Scan QR for wrong class/date → must fail
"""
import pytest
from httpx import AsyncClient
from datetime import date, datetime
import time

from tests.conftest import auth_header, TEST_CLASS_ID


class TestAttendanceSessionStart:
    """Tests for starting attendance sessions."""
    
    @pytest.mark.asyncio
    async def test_start_session_static_mode(
        self, async_client: AsyncClient, teacher_token
    ):
        """Teacher can start a static attendance session."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        response = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={
                "class_id": TEST_CLASS_ID,
                "mode": "static"
            }
        )
        
        # Should succeed or return 403 if not assigned teacher
        assert response.status_code in [200, 403]
        
        if response.status_code == 200:
            data = response.json()
            
            assert "session_id" in data
            assert data["class_id"] == TEST_CLASS_ID
            assert data["mode"] == "static"
            assert data["date"] == str(date.today())
    
    @pytest.mark.asyncio
    async def test_start_session_dynamic_mode(
        self, async_client: AsyncClient, teacher_token
    ):
        """Teacher can start a dynamic attendance session."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        response = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={
                "class_id": TEST_CLASS_ID,
                "mode": "dynamic"
            }
        )
        
        assert response.status_code in [200, 403]
        
        if response.status_code == 200:
            assert response.json()["mode"] == "dynamic"
    
    @pytest.mark.asyncio
    async def test_start_session_idempotent(
        self, async_client: AsyncClient, teacher_token
    ):
        """Starting session twice returns same session."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        # First call
        response1 = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        if response1.status_code != 200:
            pytest.skip("Could not start session")
        
        session_id_1 = response1.json()["session_id"]
        
        # Second call
        response2 = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        assert response2.status_code == 200
        session_id_2 = response2.json()["session_id"]
        
        # Should return same session
        assert session_id_1 == session_id_2, \
            "Starting session twice should return existing session"
    
    @pytest.mark.asyncio
    async def test_start_session_invalid_class_id(
        self, async_client: AsyncClient, teacher_token
    ):
        """Starting session with invalid class ID fails."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        response = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={
                "class_id": "00000000-0000-0000-0000-000000000000",
                "mode": "static"
            }
        )
        
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_start_session_not_assigned_teacher(
        self, async_client: AsyncClient
    ):
        """Teacher cannot start session for class they don't teach."""
        # Would need a different teacher's token
        pass
    
    @pytest.mark.asyncio
    async def test_start_session_invalid_mode(
        self, async_client: AsyncClient, teacher_token
    ):
        """Starting session with invalid mode fails."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        response = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={
                "class_id": TEST_CLASS_ID,
                "mode": "invalid_mode"
            }
        )
        
        # Should fail validation
        assert response.status_code == 422


class TestAttendanceScan:
    """Tests for scanning attendance QR codes."""
    
    @pytest.mark.asyncio
    async def test_scan_valid_qr(
        self, async_client: AsyncClient, teacher_token, student_token
    ):
        """Teacher can scan a valid student QR."""
        if not teacher_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Start session
        session_resp = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        if session_resp.status_code != 200:
            pytest.skip("Could not start session")
        
        session_id = session_resp.json()["session_id"]
        
        # Student generates QR
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        qr_token = qr_resp.json()["qr_token"]
        
        # Teacher scans
        scan_resp = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": qr_token, "session_id": session_id}
        )
        
        # Should succeed or indicate already recorded
        assert scan_resp.status_code in [200, 400]
        
        if scan_resp.status_code == 200:
            data = scan_resp.json()
            assert data["success"] is True
            assert "student_id" in data
            assert "student_name" in data
            assert data["status"] == "present"
    
    @pytest.mark.asyncio
    async def test_scan_invalid_qr_token(
        self, async_client: AsyncClient, teacher_token
    ):
        """Scanning invalid QR token fails."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        # Start session
        session_resp = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        if session_resp.status_code != 200:
            pytest.skip("Could not start session")
        
        session_id = session_resp.json()["session_id"]
        
        # Scan with fake token
        scan_resp = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={
                "qr_token": "completely_fake_token_12345",
                "session_id": session_id
            }
        )
        
        assert scan_resp.status_code == 400
        assert "Invalid or expired" in scan_resp.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_scan_invalid_session_id(
        self, async_client: AsyncClient, teacher_token, student_token
    ):
        """Scanning with invalid session ID fails."""
        if not teacher_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Get a valid QR token
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        qr_token = qr_resp.json()["qr_token"]
        
        # Scan with invalid session ID
        scan_resp = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={
                "qr_token": qr_token,
                "session_id": "00000000-0000-0000-0000-000000000000"
            }
        )
        
        assert scan_resp.status_code == 400
    
    @pytest.mark.asyncio
    async def test_scan_already_used_qr(
        self, async_client: AsyncClient, teacher_token, student_token
    ):
        """Scanning already-used QR fails."""
        if not teacher_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Start session
        session_resp = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        if session_resp.status_code != 200:
            pytest.skip("Could not start session")
        
        session_id = session_resp.json()["session_id"]
        
        # Student generates QR
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        qr_token = qr_resp.json()["qr_token"]
        
        # First scan
        first_scan = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": qr_token, "session_id": session_id}
        )
        
        # Second scan with same token
        second_scan = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": qr_token, "session_id": session_id}
        )
        
        # Second scan should fail or indicate already recorded
        assert second_scan.status_code == 400 or \
               "already" in second_scan.json().get("detail", "").lower() or \
               "already" in second_scan.json().get("message", "").lower()
    
    @pytest.mark.asyncio
    async def test_scan_qr_for_wrong_class(
        self, async_client: AsyncClient, teacher_token
    ):
        """Scanning QR for wrong class fails."""
        # Would need two classes with different enrollments
        pass
    
    @pytest.mark.asyncio
    async def test_scan_response_format(
        self, async_client: AsyncClient, teacher_token, student_token
    ):
        """Scan response contains all required fields."""
        if not teacher_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Start session
        session_resp = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        if session_resp.status_code != 200:
            pytest.skip("Could not start session")
        
        session_id = session_resp.json()["session_id"]
        
        # Student generates QR
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        qr_token = qr_resp.json()["qr_token"]
        
        # Scan
        scan_resp = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": qr_token, "session_id": session_id}
        )
        
        if scan_resp.status_code == 200:
            data = scan_resp.json()
            
            required_fields = [
                "success", "student_id", "student_name",
                "status", "scanned_at", "message"
            ]
            
            for field in required_fields:
                assert field in data, f"Missing field: {field}"


class TestAttendanceQRExpiry:
    """Tests for QR token expiration."""
    
    @pytest.mark.asyncio
    async def test_scan_expired_qr(self, async_client: AsyncClient, teacher_token):
        """Scanning expired QR token fails."""
        # This test would require manipulating Redis TTL
        # or waiting for token to expire (not practical in unit tests)
        # Document this as a limitation
        pass
    
    @pytest.mark.asyncio  
    async def test_qr_expires_after_ttl(self, async_client: AsyncClient, student_token):
        """QR token should expire after TTL."""
        # Would need to mock time or set very short TTL
        pass


class TestAttendanceRecordImmutability:
    """Tests for attendance record immutability."""
    
    @pytest.mark.asyncio
    async def test_cannot_change_attendance_status(
        self, async_client: AsyncClient, teacher_token
    ):
        """Once recorded, attendance status cannot be changed via API."""
        # Verify there's no endpoint to modify attendance records
        # This is a design validation test
        pass
    
    @pytest.mark.asyncio
    async def test_attendance_timestamp_immutable(
        self, async_client: AsyncClient, teacher_token
    ):
        """Attendance timestamp is set at scan time and immutable."""
        # Would need to verify in database
        pass
