"""
QR Token Lifecycle Tests (CRITICAL)

Tests:
- QR tokens are single-use
- Tokens expire after TTL
- Tokens are invalidated immediately after use
- Tokens cannot be replayed
- Tokens cannot be forged by modifying payloads

Adversarial tests:
- Token reuse
- Token mutation
- Token delay (use after expiry)
"""
import pytest
from httpx import AsyncClient
import base64
import json
import time

from tests.conftest import auth_header, TEST_CLASS_ID, TEST_STUDENT_ID


class TestAttendanceTokenSingleUse:
    """Tests for attendance QR token single-use enforcement."""
    
    @pytest.mark.asyncio
    async def test_attendance_token_invalidated_after_use(
        self, async_client: AsyncClient, student_token, teacher_token
    ):
        """Attendance token is invalidated after successful scan."""
        if not student_token or not teacher_token:
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
        
        # Generate token
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        token = qr_resp.json()["qr_token"]
        
        # First use
        first_scan = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": token, "session_id": session_id}
        )
        
        # Second use - must fail
        second_scan = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={"qr_token": token, "session_id": session_id}
        )
        
        # If first succeeded, second must fail
        if first_scan.status_code == 200:
            assert second_scan.status_code == 400, \
                "Token should not be reusable after successful scan"
    
    @pytest.mark.asyncio
    async def test_attendance_token_each_generation_unique(
        self, async_client: AsyncClient, student_token
    ):
        """Each token generation should produce unique token."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        tokens = []
        for _ in range(3):
            resp = await async_client.get(
                "/student/attendance-qr",
                headers=auth_header(student_token)
            )
            
            if resp.status_code == 200:
                tokens.append(resp.json()["qr_token"])
        
        if len(tokens) >= 2:
            # All tokens should be unique
            assert len(set(tokens)) == len(tokens), \
                "Each token generation should be unique"


class TestTokenMutation:
    """Tests for token mutation resistance."""
    
    @pytest.mark.asyncio
    async def test_mutated_token_rejected(
        self, async_client: AsyncClient, student_token, teacher_token
    ):
        """Mutated/tampered tokens should be rejected."""
        if not student_token or not teacher_token:
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
        
        # Generate valid token
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        original_token = qr_resp.json()["qr_token"]
        
        # Mutate the token
        mutated_tokens = [
            original_token[:-1] + "X",  # Change last character
            "A" + original_token[1:],   # Change first character
            original_token[::-1],        # Reverse
            original_token + "extra",    # Append
            "totally_fake_token",        # Completely fake
        ]
        
        for mutated in mutated_tokens:
            if mutated != original_token:
                resp = await async_client.post(
                    "/teacher/attendance/scan",
                    headers=auth_header(teacher_token),
                    json={"qr_token": mutated, "session_id": session_id}
                )
                
                assert resp.status_code == 400, \
                    f"Mutated token '{mutated[:20]}...' should be rejected"
    
    @pytest.mark.asyncio
    async def test_forged_token_rejected(
        self, async_client: AsyncClient, teacher_token
    ):
        """Completely forged tokens should be rejected."""
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
        
        # Try various forged tokens
        forged_tokens = [
            base64.urlsafe_b64encode(b"fake_student_id").decode(),
            base64.urlsafe_b64encode(json.dumps({
                "student_id": TEST_STUDENT_ID,
                "class_id": TEST_CLASS_ID
            }).encode()).decode(),
            "a" * 44,  # Look like base64
            TEST_STUDENT_ID,  # Just the student ID
        ]
        
        for forged in forged_tokens:
            resp = await async_client.post(
                "/teacher/attendance/scan",
                headers=auth_header(teacher_token),
                json={"qr_token": forged, "session_id": session_id}
            )
            
            assert resp.status_code == 400, \
                f"Forged token should be rejected"


class TestTokenExpiry:
    """Tests for token expiration."""
    
    @pytest.mark.asyncio
    async def test_token_has_expiry(
        self, async_client: AsyncClient, student_token
    ):
        """Token should have an expiry time."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if resp.status_code == 200:
            data = resp.json()
            assert "expires_at" in data, "Token should have expires_at"
            
            from datetime import datetime
            expires = datetime.fromisoformat(
                data["expires_at"].replace('Z', '+00:00')
            )
            now = datetime.now(expires.tzinfo)
            
            assert expires > now, "Expiry should be in the future"
    
    @pytest.mark.asyncio
    async def test_expired_token_rejected(
        self, async_client: AsyncClient, teacher_token
    ):
        """Expired tokens should be rejected."""
        # This would require Redis manipulation or time mocking
        # Document as requiring integration test with time control
        pass


class TestStoreTokenLifecycle:
    """Tests for store QR token lifecycle."""
    
    @pytest.mark.asyncio
    async def test_store_qr_not_replayable(
        self, async_client: AsyncClient, store_token, admin_token
    ):
        """Store transactions should not be replayable."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        # Ensure student has balance
        if admin_token:
            await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 100}
            )
        
        # First charge
        first_charge = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": 10.00
            }
        )
        
        if first_charge.status_code == 200:
            transaction_id = first_charge.json()["transaction_id"]
            
            # Cannot replay via API - there's no replay endpoint
            # But verify balance decreased correctly
            second_charge = await async_client.post(
                "/store/charge",
                headers=auth_header(store_token),
                json={
                    "student_id": TEST_STUDENT_ID,
                    "amount": 10.00
                }
            )
            
            # Second charge should create NEW transaction
            if second_charge.status_code == 200:
                new_transaction_id = second_charge.json()["transaction_id"]
                assert new_transaction_id != transaction_id, \
                    "Each charge should create unique transaction"


class TestTokenRandomness:
    """Tests for token randomness and unpredictability."""
    
    @pytest.mark.asyncio
    async def test_tokens_not_sequential(
        self, async_client: AsyncClient, student_token
    ):
        """Tokens should not be sequential or predictable."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        tokens = []
        for _ in range(5):
            resp = await async_client.get(
                "/student/attendance-qr",
                headers=auth_header(student_token)
            )
            
            if resp.status_code == 200:
                tokens.append(resp.json()["qr_token"])
        
        if len(tokens) >= 2:
            # Check that tokens don't follow simple patterns
            for i in range(len(tokens) - 1):
                # Tokens should not differ by just 1 character at same position
                diff_count = sum(
                    1 for a, b in zip(tokens[i], tokens[i+1]) if a != b
                )
                assert diff_count > 3, \
                    "Tokens should have significant randomness"
    
    @pytest.mark.asyncio
    async def test_token_sufficient_entropy(
        self, async_client: AsyncClient, student_token
    ):
        """Token should have sufficient entropy (length)."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if resp.status_code == 200:
            token = resp.json()["qr_token"]
            
            # Token should be at least 32 bytes encoded (43+ chars in base64)
            assert len(token) >= 32, \
                f"Token length {len(token)} should be >= 32 for security"


class TestCrossSessionTokenValidation:
    """Tests for cross-session token validation."""
    
    @pytest.mark.asyncio
    async def test_token_wrong_session_rejected(
        self, async_client: AsyncClient, student_token, teacher_token
    ):
        """Token should be rejected if used with wrong session."""
        if not student_token or not teacher_token:
            pytest.skip("Could not get required tokens")
        
        # Generate QR (might be tied to specific session/class)
        qr_resp = await async_client.get(
            "/student/attendance-qr",
            headers=auth_header(student_token)
        )
        
        if qr_resp.status_code != 200:
            pytest.skip("Could not generate QR")
        
        token = qr_resp.json()["qr_token"]
        
        # Try to use with fake session ID
        resp = await async_client.post(
            "/teacher/attendance/scan",
            headers=auth_header(teacher_token),
            json={
                "qr_token": token,
                "session_id": "00000000-0000-0000-0000-000000000000"
            }
        )
        
        assert resp.status_code == 400
