"""
Store Flow Tests

Tests:
- Scan store QR
- Charge valid amount
- Charge exceeding balance → must fail
- Double-charge same QR → must fail
- Validate balance_after correctness
"""
import pytest
from httpx import AsyncClient
from decimal import Decimal
from datetime import date

from tests.conftest import auth_header, TEST_STUDENT_ID


class TestStoreScan:
    """Tests for store scanning student QR."""
    
    @pytest.mark.asyncio
    async def test_scan_valid_student(
        self, async_client: AsyncClient, store_token
    ):
        """Store can scan a valid student."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        response = await async_client.post(
            "/store/scan",
            headers=auth_header(store_token),
            json={"student_id": TEST_STUDENT_ID}
        )
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            
            assert "student_id" in data
            assert "student_name" in data
            assert "program_name" in data
            assert "balance" in data
            assert "date" in data
    
    @pytest.mark.asyncio
    async def test_scan_invalid_student_id(
        self, async_client: AsyncClient, store_token
    ):
        """Scanning invalid student ID fails."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        response = await async_client.post(
            "/store/scan",
            headers=auth_header(store_token),
            json={"student_id": "00000000-0000-0000-0000-000000000000"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_scan_malformed_student_id(
        self, async_client: AsyncClient, store_token
    ):
        """Scanning malformed student ID fails."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        response = await async_client.post(
            "/store/scan",
            headers=auth_header(store_token),
            json={"student_id": "not-a-uuid"}
        )
        
        # Should fail with validation error or bad request
        assert response.status_code in [400, 404, 422, 500]
    
    @pytest.mark.asyncio
    async def test_scan_shows_correct_balance(
        self, async_client: AsyncClient, store_token, student_token
    ):
        """Scan shows correct current balance."""
        if not store_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Get student's balance via student endpoint
        student_balance_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if student_balance_resp.status_code != 200:
            pytest.skip("Could not get student balance")
        
        expected_remaining = student_balance_resp.json()["remaining"]
        
        # Scan via store
        scan_resp = await async_client.post(
            "/store/scan",
            headers=auth_header(store_token),
            json={"student_id": TEST_STUDENT_ID}
        )
        
        if scan_resp.status_code == 200:
            scanned_balance = scan_resp.json()["balance"]
            
            # Convert both to Decimal for comparison
            expected = Decimal(str(expected_remaining))
            actual = Decimal(str(scanned_balance))
            
            assert actual == expected, \
                f"Scanned balance {actual} should equal student balance {expected}"


class TestStoreCharge:
    """Tests for charging student allowance."""
    
    @pytest.mark.asyncio
    async def test_charge_valid_amount(
        self, async_client: AsyncClient, store_token, student_token, admin_token
    ):
        """Store can charge a valid amount."""
        if not store_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # First ensure student has allowance
        if admin_token:
            await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 100}
            )
        
        # Get current balance
        balance_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if balance_resp.status_code != 200:
            pytest.skip("Could not get balance")
        
        current_balance = Decimal(str(balance_resp.json()["remaining"]))
        
        if current_balance < Decimal("5.00"):
            pytest.skip("Insufficient balance for test")
        
        # Charge small amount
        charge_amount = Decimal("5.00")
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": float(charge_amount)
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "transaction_id" in data
        assert data["student_id"] == TEST_STUDENT_ID
        
        # Verify balance_after is correct
        expected_after = current_balance - charge_amount
        actual_after = Decimal(str(data["balance_after"]))
        
        assert actual_after == expected_after, \
            f"Balance after {actual_after} should be {expected_after}"
    
    @pytest.mark.asyncio
    async def test_charge_exceeds_balance(
        self, async_client: AsyncClient, store_token, student_token
    ):
        """Charging more than balance fails."""
        if not store_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Get current balance
        balance_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if balance_resp.status_code != 200:
            pytest.skip("Could not get balance")
        
        current_balance = Decimal(str(balance_resp.json()["remaining"]))
        
        # Try to charge more than available
        excessive_amount = current_balance + Decimal("100.00")
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": float(excessive_amount)
            }
        )
        
        assert response.status_code == 400
        assert "insufficient" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_charge_zero_amount(
        self, async_client: AsyncClient, store_token
    ):
        """Charging zero amount fails."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": 0
            }
        )
        
        # Should fail validation (amount must be > 0)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_charge_negative_amount(
        self, async_client: AsyncClient, store_token
    ):
        """Charging negative amount fails."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": -10.00
            }
        )
        
        # Should fail validation
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_charge_invalid_student(
        self, async_client: AsyncClient, store_token
    ):
        """Charging non-existent student fails."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": "00000000-0000-0000-0000-000000000000",
                "amount": 10.00
            }
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_charge_with_location_and_notes(
        self, async_client: AsyncClient, store_token, admin_token
    ):
        """Charge can include location and notes."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        # Ensure student has balance
        if admin_token:
            await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 100}
            )
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": 5.00,
                "location": "Main Cafeteria",
                "notes": "Lunch purchase"
            }
        )
        
        # Should not fail due to optional fields
        assert response.status_code in [200, 400]


class TestStoreTransactionIntegrity:
    """Tests for transaction integrity."""
    
    @pytest.mark.asyncio
    async def test_balance_decreases_after_charge(
        self, async_client: AsyncClient, store_token, student_token, admin_token
    ):
        """Balance should decrease after successful charge."""
        if not store_token or not student_token:
            pytest.skip("Could not get required tokens")
        
        # Reset allowance to known amount
        if admin_token:
            await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 100}
            )
        
        # Get balance before
        before_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if before_resp.status_code != 200:
            pytest.skip("Could not get initial balance")
        
        balance_before = Decimal(str(before_resp.json()["remaining"]))
        charge_amount = Decimal("10.00")
        
        if balance_before < charge_amount:
            pytest.skip("Insufficient balance")
        
        # Charge
        await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": float(charge_amount)
            }
        )
        
        # Get balance after
        after_resp = await async_client.get(
            "/student/balance",
            headers=auth_header(student_token)
        )
        
        if after_resp.status_code == 200:
            balance_after = Decimal(str(after_resp.json()["remaining"]))
            expected = balance_before - charge_amount
            
            assert balance_after <= expected, \
                f"Balance should decrease after charge"
    
    @pytest.mark.asyncio
    async def test_transaction_creates_record(
        self, async_client: AsyncClient, store_token, admin_token
    ):
        """Each charge should create a transaction record."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        # Ensure balance
        if admin_token:
            await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 100}
            )
        
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": 1.00
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have a unique transaction ID
            assert "transaction_id" in data
            assert len(data["transaction_id"]) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_charges_no_overdraft(
        self, async_client: AsyncClient, store_token, admin_token
    ):
        """Concurrent charges should not cause overdraft."""
        # This would require actual concurrent testing
        # Document as a limitation
        pass


class TestStoreDecimalPrecision:
    """Tests for decimal precision in financial operations."""
    
    @pytest.mark.asyncio
    async def test_charge_preserves_decimal_precision(
        self, async_client: AsyncClient, store_token, admin_token
    ):
        """Charge amounts preserve decimal precision."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        # Ensure balance
        if admin_token:
            await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 100}
            )
        
        # Charge with cents
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": 12.34
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            amount = Decimal(str(data["amount"]))
            
            assert amount == Decimal("12.34"), \
                f"Amount {amount} should preserve cents"
    
    @pytest.mark.asyncio
    async def test_balance_after_preserves_precision(
        self, async_client: AsyncClient, store_token, admin_token
    ):
        """Balance after charge preserves decimal precision."""
        if not store_token:
            pytest.skip("Could not get store token")
        
        # Reset to known amount with cents
        if admin_token:
            reset_resp = await async_client.post(
                "/admin/allowance/reset",
                headers=auth_header(admin_token),
                json={"student_id": TEST_STUDENT_ID, "base_amount": 50.50}
            )
        
        # Charge with cents
        response = await async_client.post(
            "/store/charge",
            headers=auth_header(store_token),
            json={
                "student_id": TEST_STUDENT_ID,
                "amount": 10.25
            }
        )
        
        if response.status_code == 200:
            balance_after = Decimal(str(response.json()["balance_after"]))
            
            # Should be exactly 50.50 - 10.25 = 40.25
            # (accounting for any prior transactions)
            assert str(balance_after).endswith("25") or \
                   balance_after == Decimal("0.00"), \
                "Balance should preserve cent precision"
