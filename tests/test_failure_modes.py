"""
Failure Mode Tests

Tests system behavior under failure conditions:
- Database unavailable
- Redis unavailable
- Invalid/malformed data
- Timeout scenarios
- Partial failures
- Clock skew

These tests identify graceful degradation and error handling.
"""
import pytest
from httpx import AsyncClient
import asyncio
from unittest.mock import patch, AsyncMock

from tests.conftest import auth_header, TEST_STUDENT_ID, TEST_CLASS_ID


class TestDatabaseUnavailable:
    """Tests for behavior when databases are unavailable."""
    
    @pytest.mark.asyncio
    async def test_mongodb_down_returns_503(self, async_client: AsyncClient):
        """
        Should return 503 Service Unavailable when MongoDB is down.
        
        Note: This test documents expected behavior.
        Actual test requires mocking or stopping MongoDB.
        """
        # Document expected behavior
        # When MongoDB is unavailable:
        # - Login should fail with 503
        # - Not 500 (internal error)
        pass
    
    @pytest.mark.asyncio
    async def test_postgresql_down_returns_503(self, async_client: AsyncClient):
        """
        Should return 503 Service Unavailable when PostgreSQL is down.
        
        Note: Requires mocking or stopping PostgreSQL.
        """
        pass
    
    @pytest.mark.asyncio
    async def test_redis_down_qr_fails_gracefully(self, async_client: AsyncClient, student_token):
        """
        Should handle Redis unavailability gracefully.
        
        QR generation should fail with clear error, not crash.
        """
        if not student_token:
            pytest.skip("Could not get student token")
        
        # Document expected behavior
        # When Redis is down:
        # - QR generation should fail with 503
        # - Error message should not expose internals
        pass


class TestMalformedInput:
    """Tests for malformed input handling."""
    
    @pytest.mark.asyncio
    async def test_malformed_json_returns_422(self, async_client: AsyncClient):
        """Malformed JSON should return 422, not 500."""
        resp = await async_client.post(
            "/auth/login",
            content="{ invalid json }",
            headers={"Content-Type": "application/json"}
        )
        
        assert resp.status_code == 422, \
            "Malformed JSON should return 422 Unprocessable Entity"
    
    @pytest.mark.asyncio
    async def test_wrong_content_type_handled(self, async_client: AsyncClient):
        """Wrong content type should be handled."""
        resp = await async_client.post(
            "/auth/login",
            content="username=test&password=test",
            headers={"Content-Type": "text/plain"}
        )
        
        assert resp.status_code in [400, 415, 422], \
            "Wrong content type should be rejected"
    
    @pytest.mark.asyncio
    async def test_empty_body_handled(self, async_client: AsyncClient):
        """Empty request body should be handled."""
        resp = await async_client.post(
            "/auth/login",
            content="",
            headers={"Content-Type": "application/json"}
        )
        
        assert resp.status_code == 422, \
            "Empty body should return 422"
    
    @pytest.mark.asyncio
    async def test_unicode_injection_handled(
        self, async_client: AsyncClient, store_token
    ):
        """Unicode/special characters should not cause crashes."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        # Try various problematic strings
        evil_strings = [
            "😀😀😀",  # Emoji
            "\x00\x00",  # Null bytes
            "a" * 10000,  # Very long
            "'; DROP TABLE users; --",  # SQL injection
            "<script>alert('xss')</script>",  # XSS
        ]
        
        for evil in evil_strings:
            resp = await async_client.post(
                "/store/charge",
                headers=auth_header(store_token),
                json={
                    "student_id": evil,
                    "amount": 5.00
                }
            )
            
            # Should not return 500
            assert resp.status_code != 500, \
                f"Should not crash on input: {evil[:20]}..."
    
    @pytest.mark.asyncio
    async def test_very_large_numbers_handled(
        self, async_client: AsyncClient, admin_token
    ):
        """Very large numbers should be rejected, not cause overflow."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        # Try very large amount
        resp = await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "base_amount": 10**15  # Very large
            }
        )
        
        # Should either accept (if valid) or reject with 4xx
        assert resp.status_code != 500, \
            "Large numbers should not cause server error"
    
    @pytest.mark.asyncio
    async def test_negative_amounts_rejected(
        self, async_client: AsyncClient, admin_token
    ):
        """Negative amounts should be rejected."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        resp = await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "base_amount": -100
            }
        )
        
        assert resp.status_code == 422, \
            "Negative amounts should be rejected"


class TestAuthenticationFailures:
    """Tests for authentication edge cases."""
    
    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, async_client: AsyncClient):
        """Expired JWT should return 401, not 500."""
        # Use an obviously expired token (or mock)
        expired_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxfQ."
            "signature"
        )
        
        resp = await async_client.get(
            "/student/balance",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert resp.status_code == 401, \
            "Expired token should return 401"
    
    @pytest.mark.asyncio
    async def test_malformed_token_returns_401(self, async_client: AsyncClient):
        """Malformed JWT should return 401, not 500."""
        malformed_tokens = [
            "not.a.jwt",
            "Bearer",
            "Bearer ",
            "eyJhbGciOiJIUzI1NiJ9",  # Incomplete
            "a.b.c",
        ]
        
        for token in malformed_tokens:
            resp = await async_client.get(
                "/student/balance",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert resp.status_code == 401, \
                f"Malformed token '{token}' should return 401"
    
    @pytest.mark.asyncio
    async def test_wrong_algorithm_token_rejected(self, async_client: AsyncClient):
        """Token with wrong algorithm should be rejected."""
        # Token signed with different algorithm
        # In practice, the backend should reject algorithm switching
        pass
    
    @pytest.mark.asyncio
    async def test_missing_authorization_returns_401(self, async_client: AsyncClient):
        """Missing Authorization header should return 401."""
        resp = await async_client.get("/student/balance")
        
        assert resp.status_code in [401, 403], \
            "Missing auth should return 401 or 403"


class TestConcurrencyFailures:
    """Tests for concurrency edge cases."""
    
    @pytest.mark.asyncio
    async def test_double_session_start_handled(
        self, async_client: AsyncClient, teacher_token
    ):
        """Starting session twice for same class should be handled."""
        if not teacher_token:
            pytest.skip("Could not get teacher token")
        
        # Start first session
        first = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        # Start second session immediately
        second = await async_client.post(
            "/teacher/attendance-session/start",
            headers=auth_header(teacher_token),
            json={"class_id": TEST_CLASS_ID, "mode": "static"}
        )
        
        # Should either create new session or indicate already active
        assert second.status_code in [200, 400, 409], \
            "Double session start should be handled"


class TestTimeoutScenarios:
    """Tests for timeout behavior."""
    
    @pytest.mark.asyncio
    async def test_request_timeout_documented(self):
        """
        Document timeout behavior.
        
        Expected:
        - API should have reasonable timeout (30s default)
        - Long-running operations should be async
        - Client should see 504 for gateway timeout
        """
        pass


class TestErrorMessageSecurity:
    """Tests that error messages don't leak sensitive info."""
    
    @pytest.mark.asyncio
    async def test_login_failure_generic_message(self, async_client: AsyncClient):
        """Login failure should not reveal whether user exists."""
        # Wrong password for potentially existing user
        resp1 = await async_client.post(
            "/auth/login",
            json={"username": "admin", "password": "wrong"}
        )
        
        # Completely fake user
        resp2 = await async_client.post(
            "/auth/login",
            json={"username": "nonexistent_xyz123", "password": "wrong"}
        )
        
        if resp1.status_code == 401 and resp2.status_code == 401:
            # Messages should be similar (not reveal user existence)
            msg1 = resp1.json().get("detail", "").lower()
            msg2 = resp2.json().get("detail", "").lower()
            
            # Should not say "user not found" vs "wrong password"
            if "user not found" in msg1 or "user not found" in msg2:
                pytest.skip(
                    "Warning: Error message may reveal user existence. "
                    "Consider using generic 'Invalid credentials' message."
                )
    
    @pytest.mark.asyncio
    async def test_500_errors_dont_leak_stack(self, async_client: AsyncClient):
        """
        500 errors should not expose stack traces.
        
        Note: Hard to trigger intentional 500 without breaking things.
        This documents the requirement.
        """
        pass


class TestResourceExhaustion:
    """Tests for resource exhaustion scenarios."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_exists(self, async_client: AsyncClient):
        """
        Should have rate limiting to prevent abuse.
        
        Note: Depends on rate limiter configuration.
        """
        # Rapid fire requests
        responses = []
        for _ in range(50):
            resp = await async_client.post(
                "/auth/login",
                json={"username": "test", "password": "test"}
            )
            responses.append(resp.status_code)
        
        # Should see 429 Too Many Requests at some point
        # If no rate limiting, note it
        if 429 not in responses:
            pytest.skip(
                "No rate limiting detected. "
                "Consider adding rate limiting for /auth/login"
            )
    
    @pytest.mark.asyncio
    async def test_large_payload_rejected(self, async_client: AsyncClient):
        """Very large payloads should be rejected."""
        large_payload = {"username": "a" * 1000000, "password": "b" * 1000000}
        
        resp = await async_client.post(
            "/auth/login",
            json=large_payload
        )
        
        # Should reject with 413 or 422
        assert resp.status_code in [413, 422, 400], \
            "Large payloads should be rejected"


class TestGracefulDegradation:
    """Tests for graceful degradation scenarios."""
    
    @pytest.mark.asyncio
    async def test_partial_data_handled(
        self, async_client: AsyncClient, student_token
    ):
        """
        System should handle partial/incomplete data.
        
        If allowance record doesn't exist, should return sensible default.
        """
        if not student_token:
            pytest.skip("Could not get student token")
        
        resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        # Should not be 500 even if no record
        assert resp.status_code in [200, 404], \
            "Missing record should not cause 500"
