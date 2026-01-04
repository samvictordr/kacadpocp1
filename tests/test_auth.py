"""
Authentication API Tests

Tests:
- Valid login
- Invalid credentials
- Password change flow
- Token expiration
- Unauthorized access rejection
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone
from jose import jwt

from tests.conftest import auth_header
from app.core.config import settings


class TestAuthLogin:
    """Tests for /auth/login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_valid_credentials_student(
        self, async_client: AsyncClient, test_student_credentials
    ):
        """Test login with valid student credentials."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_student_credentials["email"],
                "password": test_student_credentials["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "student"
        assert data["user_id"] is not None
        assert data["name"] == test_student_credentials["name"]
    
    @pytest.mark.asyncio
    async def test_login_valid_credentials_teacher(
        self, async_client: AsyncClient, test_teacher_credentials
    ):
        """Test login with valid teacher credentials."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_teacher_credentials["email"],
                "password": test_teacher_credentials["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["role"] == "teacher"
    
    @pytest.mark.asyncio
    async def test_login_valid_credentials_store(
        self, async_client: AsyncClient, test_store_credentials
    ):
        """Test login with valid store credentials."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_store_credentials["email"],
                "password": test_store_credentials["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["role"] == "store"
    
    @pytest.mark.asyncio
    async def test_login_valid_credentials_admin(
        self, async_client: AsyncClient, test_admin_credentials
    ):
        """Test login with valid admin credentials."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_admin_credentials["email"],
                "password": test_admin_credentials["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["role"] == "admin"
    
    @pytest.mark.asyncio
    async def test_login_invalid_email(self, async_client: AsyncClient):
        """Test login with non-existent email."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": "nonexistent@academy.edu",
                "password": "anypassword"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_invalid_password(
        self, async_client: AsyncClient, test_student_credentials
    ):
        """Test login with wrong password."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_student_credentials["email"],
                "password": "wrongpassword123"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_empty_credentials(self, async_client: AsyncClient):
        """Test login with empty credentials."""
        response = await async_client.post(
            "/auth/login",
            json={"email": "", "password": ""}
        )
        
        # Should fail validation
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self, async_client: AsyncClient):
        """Test login with invalid email format."""
        response = await async_client.post(
            "/auth/login",
            json={"email": "notanemail", "password": "password123"}
        )
        
        # Should fail pydantic email validation
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_sql_injection_attempt(self, async_client: AsyncClient):
        """Test login resists SQL injection."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": "admin@academy.edu' OR '1'='1",
                "password": "password' OR '1'='1"
            }
        )
        
        # Should fail gracefully (email validation or auth failure)
        assert response.status_code in [401, 422]
    
    @pytest.mark.asyncio
    async def test_login_returns_valid_jwt(
        self, async_client: AsyncClient, test_student_credentials
    ):
        """Test that login returns a valid, decodable JWT."""
        response = await async_client.post(
            "/auth/login",
            json={
                "email": test_student_credentials["email"],
                "password": test_student_credentials["password"]
            }
        )
        
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        # Decode and validate JWT structure
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        assert payload["sub"] == test_student_credentials["email"]
        assert payload["role"] == "student"
        assert "user_id" in payload
        assert "exp" in payload
        assert "iat" in payload


class TestTokenValidation:
    """Tests for JWT token validation and expiration."""
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_without_token(
        self, async_client: AsyncClient
    ):
        """Test accessing protected endpoint without token returns 403."""
        response = await async_client.get("/student/balance")
        
        # FastAPI's HTTPBearer returns 403 when no auth header
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_with_invalid_token(
        self, async_client: AsyncClient
    ):
        """Test accessing protected endpoint with invalid token returns 401."""
        response = await async_client.get(
            "/student/balance",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_access_protected_endpoint_with_malformed_header(
        self, async_client: AsyncClient
    ):
        """Test accessing protected endpoint with malformed auth header."""
        response = await async_client.get(
            "/student/balance",
            headers={"Authorization": "NotBearer sometoken"}
        )
        
        # Should reject malformed header
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_access_with_expired_token(self, async_client: AsyncClient):
        """Test that expired tokens are rejected."""
        from app.core.security import create_access_token
        
        # Create a token that's already expired
        expired_token = create_access_token(
            subject="test@test.com",
            user_id="some-uuid",
            role="student",
            expires_delta=timedelta(seconds=-10)  # Expired 10 seconds ago
        )
        
        response = await async_client.get(
            "/student/balance",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_token_with_tampered_signature(
        self, async_client: AsyncClient, student_token
    ):
        """Test that tampered tokens are rejected."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        # Tamper with the token signature
        parts = student_token.rsplit('.', 1)
        tampered_token = parts[0] + ".tampered_signature"
        
        response = await async_client.get(
            "/student/balance",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        
        assert response.status_code == 401


class TestPasswordChange:
    """Tests for password change functionality."""
    
    @pytest.mark.asyncio
    async def test_change_password_valid(
        self, async_client: AsyncClient, test_student_credentials
    ):
        """Test password change with valid current password."""
        # First login to get token
        login_resp = await async_client.post(
            "/auth/login",
            json={
                "email": test_student_credentials["email"],
                "password": test_student_credentials["password"]
            }
        )
        
        if login_resp.status_code != 200:
            pytest.skip("Could not login")
        
        token = login_resp.json()["access_token"]
        
        # Try to change password
        response = await async_client.post(
            "/auth/change-password",
            headers=auth_header(token),
            json={
                "current_password": test_student_credentials["password"],
                "new_password": "newpassword123"
            }
        )
        
        # Should succeed
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Change back to original for other tests
        await async_client.post(
            "/auth/change-password",
            headers=auth_header(token),
            json={
                "current_password": "newpassword123",
                "new_password": test_student_credentials["password"]
            }
        )
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self, async_client: AsyncClient, student_token
    ):
        """Test password change with wrong current password fails."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.post(
            "/auth/change-password",
            headers=auth_header(student_token),
            json={
                "current_password": "wrongpassword",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_change_password_weak_new_password(
        self, async_client: AsyncClient, student_token, test_student_credentials
    ):
        """Test password change with weak new password fails."""
        if not student_token:
            pytest.skip("Could not get student token")
        
        response = await async_client.post(
            "/auth/change-password",
            headers=auth_header(student_token),
            json={
                "current_password": test_student_credentials["password"],
                "new_password": "short"  # Less than 8 chars
            }
        )
        
        # Should fail validation
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_change_password_without_auth(self, async_client: AsyncClient):
        """Test password change without authentication fails."""
        response = await async_client.post(
            "/auth/change-password",
            json={
                "current_password": "any",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == 403
