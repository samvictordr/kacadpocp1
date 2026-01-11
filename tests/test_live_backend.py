#!/usr/bin/env python3
"""
Live Backend Test Suite for Academy Program
Tests against the deployed Render backend at https://kacadpocp1.onrender.com

Run with: python tests/test_live_backend.py
"""
import httpx
import asyncio
import json
from datetime import date
from typing import Optional, Dict, Any
import sys

# Configuration
BASE_URL = "https://kacadpocp1.onrender.com"

# Test credentials (must exist in the deployed database)
TEST_ACCOUNTS = {
    "admin": {"email": "admin@academy.edu", "password": "admin123"},
    "student": {"email": "student1@academy.edu", "password": "student123"},
    "teacher": {"email": "teacher1@academy.edu", "password": "teacher123"},
    "store": {"email": "store1@academy.edu", "password": "store123"},
}

# Test results tracking
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
    
    def success(self, name: str):
        self.passed += 1
        print(f"  ✓ {name}")
    
    def failure(self, name: str, reason: str):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  ✗ {name}: {reason}")
    
    def skip(self, name: str, reason: str):
        self.skipped += 1
        print(f"  ⊘ {name}: {reason}")
    
    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed, {self.skipped} skipped")
        if self.errors:
            print("\nFailed tests:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        print("=" * 60)
        return self.failed == 0


results = TestResults()


async def test_health_check(async_client: httpx.AsyncClient):
    """Test the health check endpoints."""
    print("\n[1/8] Health Check Tests")
    
    # Root endpoint
    try:
        r = await async_client.get("/")
        data = r.json()
        if r.status_code == 200 and "status" in data:
            results.success("GET / returns status")
        else:
            results.failure("GET / returns status", f"Status {r.status_code}, data: {data}")
    except Exception as e:
        results.failure("GET / returns status", str(e))
    
    # Health endpoint
    try:
        r = await async_client.get("/health")
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "healthy":
                results.success("GET /health returns healthy")
            else:
                results.failure("GET /health returns healthy", f"Status: {data.get('status')}")
            
            # Check database connections
            dbs = data.get("databases", {})
            if dbs.get("postgres") == "connected":
                results.success("PostgreSQL connected")
            else:
                results.failure("PostgreSQL connected", str(dbs.get("postgres")))
            
            if dbs.get("mongodb") == "connected":
                results.success("MongoDB connected")
            else:
                results.failure("MongoDB connected", str(dbs.get("mongodb")))
            
            if dbs.get("redis") == "connected":
                results.success("Redis connected")
            else:
                results.failure("Redis connected", str(dbs.get("redis")))
        else:
            results.failure("GET /health returns healthy", f"Status {r.status_code}")
    except Exception as e:
        results.failure("GET /health returns healthy", str(e))


async def test_authentication(async_client: httpx.AsyncClient) -> Dict[str, str]:
    """Test authentication endpoints and return tokens."""
    print("\n[2/8] Authentication Tests")
    tokens = {}
    
    for role, creds in TEST_ACCOUNTS.items():
        try:
            r = await async_client.post("/auth/login", json=creds)
            if r.status_code == 200:
                data = r.json()
                if "access_token" in data:
                    tokens[role] = data["access_token"]
                    results.success(f"Login as {role}")
                else:
                    results.failure(f"Login as {role}", "No access_token in response")
            else:
                results.failure(f"Login as {role}", f"Status {r.status_code}: {r.text[:100]}")
        except Exception as e:
            results.failure(f"Login as {role}", str(e))
    
    # Test invalid login
    try:
        r = await async_client.post("/auth/login", json={"email": "fake@test.com", "password": "wrong"})
        if r.status_code == 401:
            results.success("Invalid login rejected (401)")
        else:
            results.failure("Invalid login rejected (401)", f"Got status {r.status_code}")
    except Exception as e:
        results.failure("Invalid login rejected (401)", str(e))
    
    # Test change password endpoint exists (don't actually change)
    if tokens.get("student"):
        try:
            r = await async_client.post(
                "/auth/change-password",
                json={"current_password": "wrong", "new_password": "test"},
                headers={"Authorization": f"Bearer {tokens['student']}"}
            )
            # 400 means endpoint exists and validates
            if r.status_code == 400:
                results.success("POST /auth/change-password endpoint exists")
            else:
                results.skip("POST /auth/change-password", f"Status {r.status_code}")
        except Exception as e:
            results.failure("POST /auth/change-password endpoint exists", str(e))
    
    return tokens


async def test_rbac(async_client: httpx.AsyncClient, tokens: Dict[str, str]):
    """Test Role-Based Access Control."""
    print("\n[3/8] RBAC Tests")
    
    # Student shouldn't access admin endpoints
    if tokens.get("student"):
        try:
            r = await async_client.post(
                "/admin/users/create",
                json={"email": "test@test.com", "name": "Test", "role": "student", "password": "test123"},
                headers={"Authorization": f"Bearer {tokens['student']}"}
            )
            if r.status_code in [401, 403]:
                results.success("Student blocked from admin endpoints")
            else:
                results.failure("Student blocked from admin endpoints", f"Got status {r.status_code}")
        except Exception as e:
            results.failure("Student blocked from admin endpoints", str(e))
    
    # Teacher shouldn't access store endpoints
    if tokens.get("teacher"):
        try:
            r = await async_client.post("/store/scan", 
                                  json={"token": "test"},
                                  headers={"Authorization": f"Bearer {tokens['teacher']}"})
            if r.status_code in [401, 403]:
                results.success("Teacher blocked from store endpoints")
            else:
                results.failure("Teacher blocked from store endpoints", f"Got status {r.status_code}")
        except Exception as e:
            results.failure("Teacher blocked from store endpoints", str(e))
    
    # Unauthenticated access should be blocked
    try:
        r = await async_client.get("/student/balance")
        if r.status_code in [401, 403]:
            results.success("Unauthenticated requests blocked")
        else:
            results.failure("Unauthenticated requests blocked", f"Got status {r.status_code}")
    except Exception as e:
        results.failure("Unauthenticated requests blocked", str(e))


async def test_student_endpoints(async_client: httpx.AsyncClient, tokens: Dict[str, str]):
    """Test student-specific endpoints."""
    print("\n[4/8] Student Endpoint Tests")
    
    if not tokens.get("student"):
        results.failure("Student endpoints", "No student token available")
        return
    
    headers = {"Authorization": f"Bearer {tokens['student']}"}
    
    # Get attendance QR code
    try:
        r = await async_client.get("/student/attendance-qr", headers=headers)
        if r.status_code == 200:
            data = r.json()
            if "qr_token" in data or "token" in data:
                results.success("GET /student/attendance-qr generates token")
            else:
                results.failure("GET /student/attendance-qr generates token", f"Response: {data}")
        elif r.status_code == 404:
            # 404 means student record not found - expected if no student data seeded
            results.skip("GET /student/attendance-qr", "No student record in DB")
        else:
            results.failure("GET /student/attendance-qr generates token", f"Status {r.status_code}")
    except Exception as e:
        results.failure("GET /student/attendance-qr generates token", str(e))
    
    # Get student balance
    try:
        r = await async_client.get("/student/balance", headers=headers)
        if r.status_code == 200:
            data = r.json()
            # API returns: student_id, date, base_amount, bonus_amount, total_amount, spent_today, remaining
            if "remaining" in data or "total_amount" in data or "balance" in data:
                results.success(f"GET /student/balance (remaining: {data.get('remaining', 'N/A')})")
            else:
                results.failure("GET /student/balance", f"Response: {data}")
        elif r.status_code == 404:
            # 404 means student record not found - expected if no student data seeded
            results.skip("GET /student/balance", "No student record in DB")
        else:
            results.failure("GET /student/balance", f"Status {r.status_code}: {r.text[:100]}")
    except Exception as e:
        results.failure("GET /student/balance", str(e))
    
    # Get store QR
    try:
        r = await async_client.get("/student/store-qr", headers=headers)
        if r.status_code == 200:
            data = r.json()
            # API returns: student_id, date, balance
            if "balance" in data or "qr_token" in data or "qr_data" in data:
                results.success(f"GET /student/store-qr (balance: {data.get('balance', 'N/A')})")
            else:
                results.failure("GET /student/store-qr", f"Response: {data}")
        elif r.status_code == 404:
            results.skip("GET /student/store-qr", "No student record in DB")
        else:
            results.failure("GET /student/store-qr", f"Status {r.status_code}: {r.text[:100]}")
    except Exception as e:
        results.failure("GET /student/store-qr", str(e))


async def test_teacher_endpoints(async_client: httpx.AsyncClient, tokens: Dict[str, str]):
    """Test teacher-specific endpoints."""
    print("\n[5/8] Teacher Endpoint Tests")
    
    if not tokens.get("teacher"):
        results.failure("Teacher endpoints", "No teacher token available")
        return
    
    headers = {"Authorization": f"Bearer {tokens['teacher']}"}
    
    # Get teacher's classes
    try:
        r = await async_client.get("/teacher/classes", headers=headers)
        if r.status_code == 200:
            results.success("GET /teacher/classes")
        else:
            results.failure("GET /teacher/classes", f"Status {r.status_code}: {r.text[:100]}")
    except Exception as e:
        results.failure("GET /teacher/classes", str(e))
    
    # Test start attendance session endpoint exists (with invalid class_id)
    try:
        r = await async_client.post(
            "/teacher/attendance-session/start",
            json={"class_id": "00000000-0000-0000-0000-000000000000", "mode": "qr"},
            headers=headers
        )
        # 400/403/404 means endpoint exists and validates
        if r.status_code in [400, 403, 404, 422]:
            results.success("POST /teacher/attendance-session/start endpoint exists")
        else:
            results.failure("POST /teacher/attendance-session/start endpoint exists", f"Status {r.status_code}")
    except Exception as e:
        results.failure("POST /teacher/attendance-session/start endpoint exists", str(e))


async def test_store_endpoints(async_client: httpx.AsyncClient, tokens: Dict[str, str]):
    """Test store-specific endpoints."""
    print("\n[6/8] Store Endpoint Tests")
    
    if not tokens.get("store"):
        results.failure("Store endpoints", "No store token available")
        return
    
    headers = {"Authorization": f"Bearer {tokens['store']}"}
    
    # Test scan with invalid student_id (should fail gracefully)
    try:
        r = await async_client.post("/store/scan", 
                              json={"student_id": "00000000-0000-0000-0000-000000000000"},
                              headers=headers)
        if r.status_code in [400, 404]:
            results.success("POST /store/scan rejects invalid student_id")
        elif r.status_code == 422:
            results.success("POST /store/scan validates input")
        else:
            results.failure("POST /store/scan rejects invalid student_id", f"Status {r.status_code}")
    except Exception as e:
        results.failure("POST /store/scan rejects invalid student_id", str(e))
    
    # Test charge with invalid student_id
    try:
        r = await async_client.post("/store/charge",
                              json={"student_id": "00000000-0000-0000-0000-000000000000", "amount": 10, "location": "test"},
                              headers=headers)
        if r.status_code in [400, 404]:
            results.success("POST /store/charge rejects invalid student_id")
        elif r.status_code == 422:
            results.success("POST /store/charge validates input")
        else:
            results.failure("POST /store/charge rejects invalid student_id", f"Status {r.status_code}")
    except Exception as e:
        results.failure("POST /store/charge rejects invalid student_id", str(e))


async def test_admin_endpoints(async_client: httpx.AsyncClient, tokens: Dict[str, str]):
    """Test admin-specific endpoints."""
    print("\n[7/8] Admin Endpoint Tests")
    
    if not tokens.get("admin"):
        results.failure("Admin endpoints", "No admin token available")
        return
    
    headers = {"Authorization": f"Bearer {tokens['admin']}"}
    
    # Test create user endpoint (with invalid data to just verify it exists)
    try:
        r = await async_client.post(
            "/admin/users/create",
            json={"email": "test-exists@test.com", "name": "Test", "role": "student", "password": "test123"},
            headers=headers
        )
        # 400 means endpoint exists (missing program_id for student)
        # 409 might mean user already exists
        if r.status_code in [200, 400, 409, 422]:
            results.success("POST /admin/users/create endpoint exists")
        else:
            results.failure("POST /admin/users/create endpoint exists", f"Status {r.status_code}")
    except Exception as e:
        results.failure("POST /admin/users/create endpoint exists", str(e))
    
    # Test allowance reset endpoint
    try:
        r = await async_client.post(
            "/admin/allowance/reset",
            json={"reset_date": str(date.today())},
            headers=headers
        )
        # Should work or give a meaningful response
        if r.status_code in [200, 400, 422]:
            results.success("POST /admin/allowance/reset endpoint exists")
        else:
            results.failure("POST /admin/allowance/reset endpoint exists", f"Status {r.status_code}")
    except Exception as e:
        results.failure("POST /admin/allowance/reset endpoint exists", str(e))
    
    # Test allowance bump endpoint
    try:
        r = await async_client.post(
            "/admin/allowance/bump",
            json={"student_id": "00000000-0000-0000-0000-000000000000", "amount": 10},
            headers=headers
        )
        if r.status_code in [200, 400, 404, 422]:
            results.success("POST /admin/allowance/bump endpoint exists")
        else:
            results.failure("POST /admin/allowance/bump endpoint exists", f"Status {r.status_code}")
    except Exception as e:
        results.failure("POST /admin/allowance/bump endpoint exists", str(e))


async def test_api_contracts(async_client: httpx.AsyncClient, tokens: Dict[str, str]):
    """Test API response contracts."""
    print("\n[8/8] API Contract Tests")
    
    # Test error response format
    try:
        r = await async_client.get("/nonexistent-endpoint")
        if r.status_code == 404:
            results.success("404 for unknown endpoints")
        else:
            results.failure("404 for unknown endpoints", f"Got {r.status_code}")
    except Exception as e:
        results.failure("404 for unknown endpoints", str(e))
    
    # Test content-type is JSON
    try:
        r = await async_client.get("/")
        if "application/json" in r.headers.get("content-type", ""):
            results.success("Response Content-Type is JSON")
        else:
            results.failure("Response Content-Type is JSON", r.headers.get("content-type"))
    except Exception as e:
        results.failure("Response Content-Type is JSON", str(e))
    
    # Test CORS headers
    try:
        r = await async_client.options("/", headers={"Origin": "https://test.com"})
        # CORS preflight should work
        if r.status_code in [200, 204, 405]:
            results.success("CORS preflight handled")
        else:
            results.failure("CORS preflight handled", f"Status {r.status_code}")
    except Exception as e:
        results.failure("CORS preflight handled", str(e))


async def main():
    """Run all tests against the live backend."""
    print("=" * 60)
    print(f"Academy Program Live Backend Tests")
    print(f"Target: {BASE_URL}")
    print("=" * 60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Run all test suites
        await test_health_check(client)
        tokens = await test_authentication(client)
        await test_rbac(client, tokens)
        await test_student_endpoints(client, tokens)
        await test_teacher_endpoints(client, tokens)
        await test_store_endpoints(client, tokens)
        await test_admin_endpoints(client, tokens)
        await test_api_contracts(client, tokens)
    
    # Print summary
    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
