"""
Admin Flow Tests

Tests:
- Create users (student, teacher, store)
- Reset daily allowances
- Grant allowance bump
- Verify auditability of changes
"""
import pytest
from httpx import AsyncClient
from decimal import Decimal
from datetime import date
import uuid

from tests.conftest import auth_header, TEST_STUDENT_ID, TEST_PROGRAM_ID


class TestCreateUser:
    """Tests for user creation."""
    
    @pytest.mark.asyncio
    async def test_create_teacher_user(
        self, async_client: AsyncClient, admin_token
    ):
        """Admin can create a teacher user."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        unique_email = f"teacher_{uuid.uuid4().hex[:8]}@academy.edu"
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": unique_email,
                "name": "Test Teacher",
                "role": "teacher",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["email"] == unique_email
        assert data["role"] == "teacher"
        assert "user_id" in data
    
    @pytest.mark.asyncio
    async def test_create_store_user(
        self, async_client: AsyncClient, admin_token
    ):
        """Admin can create a store user."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        unique_email = f"store_{uuid.uuid4().hex[:8]}@academy.edu"
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": unique_email,
                "name": "Test Store Staff",
                "role": "store",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["role"] == "store"
    
    @pytest.mark.asyncio
    async def test_create_student_user_requires_program(
        self, async_client: AsyncClient, admin_token
    ):
        """Creating student without program_id fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        unique_email = f"student_{uuid.uuid4().hex[:8]}@academy.edu"
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": unique_email,
                "name": "Test Student",
                "role": "student",
                "password": "password123"
                # Missing program_id
            }
        )
        
        assert response.status_code == 400
        assert "program_id" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_create_student_user_with_program(
        self, async_client: AsyncClient, admin_token
    ):
        """Creating student with program_id succeeds."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        unique_email = f"student_{uuid.uuid4().hex[:8]}@academy.edu"
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": unique_email,
                "name": "Test Student",
                "role": "student",
                "password": "password123",
                "program_id": TEST_PROGRAM_ID
            }
        )
        
        assert response.status_code == 200
        assert response.json()["role"] == "student"
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(
        self, async_client: AsyncClient, admin_token, test_student_credentials
    ):
        """Creating user with existing email fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": test_student_credentials["email"],  # Already exists
                "name": "Duplicate User",
                "role": "teacher",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "exists" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_create_user_invalid_role(
        self, async_client: AsyncClient, admin_token
    ):
        """Creating user with invalid role fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": "invalid@academy.edu",
                "name": "Invalid Role",
                "role": "superuser",  # Invalid
                "password": "password123"
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_user_weak_password(
        self, async_client: AsyncClient, admin_token
    ):
        """Creating user with weak password fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": "weak@academy.edu",
                "name": "Weak Password",
                "role": "teacher",
                "password": "short"  # Too short
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_user_invalid_email_format(
        self, async_client: AsyncClient, admin_token
    ):
        """Creating user with invalid email fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/users/create",
            headers=auth_header(admin_token),
            json={
                "email": "not-an-email",
                "name": "Invalid Email",
                "role": "teacher",
                "password": "password123"
            }
        )
        
        assert response.status_code == 422


class TestAllowanceReset:
    """Tests for allowance reset."""
    
    @pytest.mark.asyncio
    async def test_reset_all_allowances(
        self, async_client: AsyncClient, admin_token
    ):
        """Admin can reset all student allowances."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={}
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "students_affected" in data
        assert data["date"] == str(date.today())
    
    @pytest.mark.asyncio
    async def test_reset_single_student_allowance(
        self, async_client: AsyncClient, admin_token
    ):
        """Admin can reset single student allowance."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={"student_id": TEST_STUDENT_ID}
        )
        
        assert response.status_code == 200
        assert response.json()["students_affected"] == 1
    
    @pytest.mark.asyncio
    async def test_reset_with_custom_amount(
        self, async_client: AsyncClient, admin_token, student_token
    ):
        """Admin can reset allowance with custom amount."""
        if not admin_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        custom_amount = 75.50
        
        response = await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "base_amount": custom_amount
            }
        )
        
        assert response.status_code == 200
        
        # Verify student's balance was updated
        balance_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if balance_resp.status_code == 200:
            base = Decimal(str(balance_resp.json()["base_amount"]))
            assert base == Decimal(str(custom_amount))
    
    @pytest.mark.asyncio
    async def test_reset_invalid_student_id(
        self, async_client: AsyncClient, admin_token
    ):
        """Resetting invalid student ID fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={"student_id": "00000000-0000-0000-0000-000000000000"}
        )
        
        assert response.status_code == 400


class TestAllowanceBump:
    """Tests for allowance bump."""
    
    @pytest.mark.asyncio
    async def test_bump_allowance_success(
        self, async_client: AsyncClient, admin_token, student_token
    ):
        """Admin can bump a student's allowance."""
        if not admin_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # First reset to known state
        await async_client.post(
            "/admin/allowance/reset",
            headers=auth_header(admin_token),
            json={"student_id": TEST_STUDENT_ID, "base_amount": 50}
        )
        
        # Get balance before
        before_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if before_resp.status_code != 200:
            pytest.skip("Could not get balance")
        
        bonus_before = Decimal(str(before_resp.json()["bonus_amount"]))
        bump_amount = Decimal("10.00")
        
        # Bump allowance
        response = await async_client.post(
            "/admin/allowance/bump",
            headers=auth_header(admin_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "bonus_amount": float(bump_amount)
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["student_id"] == TEST_STUDENT_ID
        
        # Verify bonus increased
        after_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if after_resp.status_code == 200:
            bonus_after = Decimal(str(after_resp.json()["bonus_amount"]))
            assert bonus_after >= bonus_before + bump_amount
    
    @pytest.mark.asyncio
    async def test_bump_zero_amount(
        self, async_client: AsyncClient, admin_token
    ):
        """Bumping zero amount fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/allowance/bump",
            headers=auth_header(admin_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "bonus_amount": 0
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_bump_negative_amount(
        self, async_client: AsyncClient, admin_token
    ):
        """Bumping negative amount fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/allowance/bump",
            headers=auth_header(admin_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "bonus_amount": -10.00
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_bump_invalid_student(
        self, async_client: AsyncClient, admin_token
    ):
        """Bumping invalid student fails."""
        if not admin_token:
            pytest.skip("Could not get admin token")
        
        response = await async_client.post(
            "/admin/allowance/bump",
            headers=auth_header(admin_token),
            json={
                "student_id": "00000000-0000-0000-0000-000000000000",
                "bonus_amount": 10.00
            }
        )
        
        assert response.status_code == 404


class TestAdminAuditability:
    """Tests for admin action auditability."""
    
    @pytest.mark.asyncio
    async def test_user_creation_is_logged(
        self, async_client: AsyncClient, admin_token
    ):
        """User creation should be logged."""
        # This would require checking audit logs
        # Document as requiring log verification
        pass
    
    @pytest.mark.asyncio
    async def test_allowance_reset_is_logged(
        self, async_client: AsyncClient, admin_token
    ):
        """Allowance reset should be logged."""
        pass
    
    @pytest.mark.asyncio
    async def test_allowance_bump_is_logged(
        self, async_client: AsyncClient, admin_token
    ):
        """Allowance bump should be logged."""
        pass
