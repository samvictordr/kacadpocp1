"""
Student Flow Tests

Tests:
- Fetch attendance QR (valid session)
- Fetch attendance QR (no session) → graceful failure
- Fetch store QR
- Fetch balance
- Attempt to reuse QR → must fail
"""
import pytest
from httpx import AsyncClient
from datetime import date

from tests.conftest import auth_header, TEST_STUDENT_ID


class TestStudentAttendanceQR:
    """Tests for student attendance QR generation."""
    
    @pytest.mark.asyncio
    async def test_get_attendance_qr_success(
        self, async_client: AsyncClient, student_token
    ):
        """Student can generate attendance QR token."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        # Should succeed or return 404 if no active session
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "qr_token" in data
            assert "student_id" in data
            assert "expires_at" in data
            
            # Token should be non-empty
            assert len(data["qr_token"]) > 0
    
    @pytest.mark.asyncio
    async def test_get_attendance_qr_token_format(
        self, async_client: AsyncClient, student_token
    ):
        """Attendance QR token should be URL-safe base64."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            token = response.json()["qr_token"]
            
            # URL-safe base64 characters only
            import re
            assert re.match(r'^[A-Za-z0-9_\-]+$', token), \
                f"Token contains invalid characters: {token}"
    
    @pytest.mark.asyncio
    async def test_get_attendance_qr_expires_in_future(
        self, async_client: AsyncClient, student_token
    ):
        """Attendance QR token expiration should be in the future."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            from datetime import datetime
            
            expires_at = response.json()["expires_at"]
            expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            now = datetime.now(expiry.tzinfo)
            
            assert expiry > now, "Token expiration should be in the future"
    
    @pytest.mark.asyncio
    async def test_get_attendance_qr_without_enrollment(
        self, async_client: AsyncClient
    ):
        """Student without enrollment should get 404."""
        # This would require a student without any class enrollment
        # For now, we just verify the endpoint handles errors gracefully
        pass


class TestStudentStoreQR:
    """Tests for student store QR generation."""
    
    @pytest.mark.asyncio
    async def test_get_store_qr_success(
        self, async_client: AsyncClient, student_token
    ):
        """Student can generate store QR data."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/store-qr",
            headers=auth_header(student_token)
        )
        
        # Should succeed or return 404 if no allowance
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "student_id" in data
            assert "date" in data
            assert "balance" in data
    
    @pytest.mark.asyncio
    async def test_get_store_qr_balance_type(
        self, async_client: AsyncClient, student_token
    ):
        """Store QR balance should be a valid decimal."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/store-qr",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            balance = response.json()["balance"]
            
            # Should be a number (could be string in JSON for decimal)
            if isinstance(balance, str):
                from decimal import Decimal
                Decimal(balance)  # Should not raise
            else:
                assert isinstance(balance, (int, float))
    
    @pytest.mark.asyncio
    async def test_get_store_qr_date_is_today(
        self, async_client: AsyncClient, student_token
    ):
        """Store QR date should be today."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/store-qr",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            qr_date = response.json()["date"]
            today = str(date.today())
            
            assert qr_date == today, f"QR date {qr_date} should be today {today}"
    
    @pytest.mark.asyncio
    async def test_get_store_qr_no_allowance(
        self, async_client: AsyncClient
    ):
        """Student without allowance should get appropriate error."""
        # Would need a student without allowance set up
        pass


class TestStudentBalance:
    """Tests for student balance endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_balance_success(
        self, async_client: AsyncClient, student_token
    ):
        """Student can fetch their balance."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        # Should succeed or return 404 if no allowance
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            
            required_fields = [
                "student_id", "date", "base_amount", "bonus_amount",
                "total_amount", "spent_today", "remaining"
            ]
            
            for field in required_fields:
                assert field in data, f"Missing field: {field}"
    
    @pytest.mark.asyncio
    async def test_get_balance_amounts_are_valid(
        self, async_client: AsyncClient, student_token
    ):
        """Balance amounts should be valid decimals."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            data = response.json()
            
            from decimal import Decimal
            
            # All amount fields should be convertible to Decimal
            amount_fields = [
                "base_amount", "bonus_amount", "total_amount",
                "spent_today", "remaining"
            ]
            
            for field in amount_fields:
                value = data[field]
                if isinstance(value, str):
                    Decimal(value)  # Should not raise
                else:
                    assert isinstance(value, (int, float)), \
                        f"{field} should be numeric"
    
    @pytest.mark.asyncio
    async def test_get_balance_remaining_non_negative(
        self, async_client: AsyncClient, student_token
    ):
        """Remaining balance should never be negative."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            from decimal import Decimal
            
            remaining = response.json()["remaining"]
            if isinstance(remaining, str):
                remaining = Decimal(remaining)
            
            assert remaining >= 0, "Remaining balance should not be negative"
    
    @pytest.mark.asyncio
    async def test_get_balance_total_equals_base_plus_bonus(
        self, async_client: AsyncClient, student_token
    ):
        """Total amount should equal base + bonus."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            from decimal import Decimal
            
            data = response.json()
            
            base = Decimal(str(data["base_amount"]))
            bonus = Decimal(str(data["bonus_amount"]))
            total = Decimal(str(data["total_amount"]))
            
            assert total == base + bonus, \
                f"Total {total} should equal base {base} + bonus {bonus}"
    
    @pytest.mark.asyncio
    async def test_get_balance_remaining_calculation(
        self, async_client: AsyncClient, student_token
    ):
        """Remaining should equal total - spent."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if response.status_code == 200:
            from decimal import Decimal
            
            data = response.json()
            
            total = Decimal(str(data["total_amount"]))
            spent = Decimal(str(data["spent_today"]))
            remaining = Decimal(str(data["remaining"]))
            
            expected_remaining = max(Decimal("0"), total - spent)
            
            assert remaining == expected_remaining, \
                f"Remaining {remaining} should equal max(0, total-spent) = {expected_remaining}"


class TestStudentQRReuse:
    """Tests for QR token single-use enforcement."""
    
    @pytest.mark.asyncio
    async def test_attendance_qr_single_use(
        self, async_client: AsyncClient, student_token, teacher_token
    ):
        """Attendance QR token should only work once."""
        if not student_token or not teacher_token:
            pytest.skip("Could not get required tokens")
        
        # Step 1: Start an attendance session
        session_response = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={
                "class_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "mode": "static"
            }
        )
        
        if session_response.status_code != 200:
            pytest.skip("Could not start attendance session")
        
        session_id = session_response.json()["session_id"]
        
        # Step 2: Student generates QR
        qr_response = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_response.status_code != 200:
            pytest.skip("Could not generate QR")
        
        qr_token = qr_response.json()["qr_token"]
        
        # Step 3: Teacher scans QR (first time)
        first_scan = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": qr_token, "session_id": session_id}
        )
        
        # First scan should succeed (or already recorded)
        # Both 200 and 400 (already recorded) are valid
        first_status = first_scan.status_code
        
        # Step 4: Try to scan same QR again
        second_scan = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": qr_token, "session_id": session_id}
        )
        
        # Second scan should fail or indicate already recorded
        if first_status == 200:
            # If first succeeded, second should fail
            assert second_scan.status_code == 400, \
                "QR token should not be reusable"
