# QA Verification Plan - University Attendance & Allowance System

## Executive Summary

This document outlines the comprehensive QA verification strategy for the Academy Program system. The system consists of:

- **FastAPI Backend** (Python 3.x)
- **PostgreSQL** - Attendance sessions, records, transactions, allowances (truth layer)
- **MongoDB** - User identity and authentication
- **Redis** - Ephemeral QR tokens with TTL
- **Three PWA Frontends** - Student, Teacher, Store

---

## 1. Test Categories

### 1.1 Authentication Tests (`test_auth.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| AUTH-001 | Valid credentials return JWT token | Critical | ✅ |
| AUTH-002 | Invalid credentials return 401 | Critical | ✅ |
| AUTH-003 | Missing credentials return 422 | High | ✅ |
| AUTH-004 | Token has correct payload structure | High | ✅ |
| AUTH-005 | Password change works | Medium | ✅ |
| AUTH-006 | Password change requires valid current password | High | ✅ |
| AUTH-007 | Token expiration is set correctly | High | ✅ |

### 1.2 Role-Based Access Control Tests (`test_rbac.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| RBAC-001 | Student cannot access teacher endpoints | Critical | ✅ |
| RBAC-002 | Student cannot access store endpoints | Critical | ✅ |
| RBAC-003 | Student cannot access admin endpoints | Critical | ✅ |
| RBAC-004 | Teacher cannot access student endpoints | Critical | ✅ |
| RBAC-005 | Teacher cannot access store endpoints | Critical | ✅ |
| RBAC-006 | Teacher cannot access admin endpoints | Critical | ✅ |
| RBAC-007 | Store cannot access student endpoints | Critical | ✅ |
| RBAC-008 | Store cannot access teacher endpoints | Critical | ✅ |
| RBAC-009 | Store cannot access admin endpoints | Critical | ✅ |
| RBAC-010 | Admin can access admin endpoints | Critical | ✅ |
| RBAC-011 | Unauthenticated requests blocked | Critical | ✅ |

### 1.3 QR Token Lifecycle Tests (`test_qr_lifecycle.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| QR-001 | Attendance token invalidated after use | Critical | ✅ |
| QR-002 | Each token generation is unique | Critical | ✅ |
| QR-003 | Mutated tokens rejected | Critical | ✅ |
| QR-004 | Forged tokens rejected | Critical | ✅ |
| QR-005 | Tokens have expiration time | High | ✅ |
| QR-006 | Tokens are not sequential | High | ✅ |
| QR-007 | Tokens have sufficient entropy | High | ✅ |
| QR-008 | Cross-session tokens rejected | High | ✅ |

### 1.4 Student Flow Tests (`test_student_flows.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| STU-001 | Can generate attendance QR | Critical | ✅ |
| STU-002 | Can get store QR data | High | ✅ |
| STU-003 | Can check balance | High | ✅ |
| STU-004 | QR token is single-use | Critical | ✅ |

### 1.5 Teacher Flow Tests (`test_teacher_flows.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| TCH-001 | Can start static session | Critical | ✅ |
| TCH-002 | Can start dynamic session | Critical | ✅ |
| TCH-003 | Can scan valid attendance QR | Critical | ✅ |
| TCH-004 | Rejects expired QR | High | ✅ |
| TCH-005 | Rejects used QR | Critical | ✅ |
| TCH-006 | Invalid session ID rejected | High | ✅ |

### 1.6 Store Flow Tests (`test_store_flows.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| STO-001 | Can scan student QR | High | ✅ |
| STO-002 | Can charge student | Critical | ✅ |
| STO-003 | Insufficient balance blocked | Critical | ✅ |
| STO-004 | Negative charge blocked | Critical | ✅ |
| STO-005 | Zero charge blocked | High | ✅ |
| STO-006 | Decimal precision maintained | High | ✅ |

### 1.7 Admin Flow Tests (`test_admin_flows.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| ADM-001 | Can create student | High | ✅ |
| ADM-002 | Can create teacher | High | ✅ |
| ADM-003 | Can create store user | High | ✅ |
| ADM-004 | Duplicate username rejected | High | ✅ |
| ADM-005 | Can reset allowance | Critical | ✅ |
| ADM-006 | Can bump allowance | High | ✅ |
| ADM-007 | Reset replaces balance | Critical | ✅ |

### 1.8 Database Consistency Tests (`test_database_consistency.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| DB-001 | Balance cannot go negative | Critical | ✅ |
| DB-002 | Decimal precision maintained | High | ✅ |
| DB-003 | Concurrent charges no race | Critical | ✅ |
| DB-004 | Transactions create records | High | ✅ |
| DB-005 | Duplicate attendance blocked | High | ✅ |
| DB-006 | Cross-DB consistency | Medium | ✅ |

### 1.9 Failure Mode Tests (`test_failure_modes.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| FAIL-001 | Malformed JSON returns 422 | High | ✅ |
| FAIL-002 | Wrong content type handled | Medium | ✅ |
| FAIL-003 | Empty body handled | Medium | ✅ |
| FAIL-004 | Unicode injection safe | High | ✅ |
| FAIL-005 | Large numbers handled | Medium | ✅ |
| FAIL-006 | Negative amounts rejected | High | ✅ |
| FAIL-007 | Expired token returns 401 | High | ✅ |
| FAIL-008 | Malformed token returns 401 | High | ✅ |
| FAIL-009 | Missing auth returns 401/403 | High | ✅ |
| FAIL-010 | Login error is generic | Medium | ✅ |

### 1.10 PWA Compliance Tests (`test_pwa_compliance.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| PWA-001 | manifest.json exists | Critical | ✅ |
| PWA-002 | manifest.json valid JSON | Critical | ✅ |
| PWA-003 | Required manifest fields | High | ✅ |
| PWA-004 | Display is standalone | Medium | ✅ |
| PWA-005 | Required icon sizes | High | ✅ |
| PWA-006 | Icon files exist | Medium | ✅ |
| PWA-007 | Viewport meta present | High | ✅ |
| PWA-008 | Manifest linked in HTML | High | ✅ |

### 1.11 Frontend Contract Tests (`test_frontend_contracts.py`)

| Test ID | Description | Priority | Status |
|---------|-------------|----------|--------|
| FE-001 | Correct login endpoint | High | ✅ |
| FE-002 | Correct attendance-qr endpoint | High | ✅ |
| FE-003 | Uses Authorization header | Critical | ✅ |
| FE-004 | Handles 401 responses | High | ✅ |
| FE-005 | Handles network errors | High | ✅ |

---

## 2. Test Execution

### 2.1 Prerequisites

```bash
# Ensure databases are running
docker ps  # Should show postgres, mongodb, redis

# Activate virtual environment
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio httpx pytest-cov
```

### 2.2 Running Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific category
pytest tests/test_auth.py -v
pytest tests/test_rbac.py -v
pytest tests/test_qr_lifecycle.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Use test runner script
chmod +x tests/run_tests.sh
./tests/run_tests.sh all
./tests/run_tests.sh coverage
```

### 2.3 Test Data Requirements

Tests require the following seed data in the databases:

| Entity | ID | Description |
|--------|-----|-------------|
| Student | `STU001` or `TEST_STUDENT_ID` | Test student account |
| Teacher | `teacher1` | Test teacher account |
| Store | `store1` | Test store account |
| Admin | `admin` | Test admin account |
| Class | `CLS001` or `TEST_CLASS_ID` | Test class |
| Program | `PRG001` or `TEST_PROGRAM_ID` | Test program |

---

## 3. Critical Verification Points

### 3.1 Security-Critical

1. **No token reuse** - QR tokens MUST be invalidated after single use
2. **No balance overflow** - Cannot charge more than available
3. **Role enforcement** - Each role strictly limited to own endpoints
4. **Token expiration** - Expired tokens MUST be rejected
5. **No replay attacks** - Same transaction cannot be repeated

### 3.2 Data Integrity-Critical

1. **Decimal precision** - Financial amounts use proper DECIMAL type
2. **Atomic transactions** - No partial charge states
3. **Audit trail** - All transactions recorded
4. **No negative balance** - System rejects over-spend

### 3.3 Availability-Critical

1. **Graceful degradation** - Clear errors when DB unavailable
2. **No 500 on bad input** - Validation returns 4xx
3. **Rate limiting** - Prevents abuse (recommended)

---

## 4. Known Issues & Recommendations

### 4.1 Issues Found

| Issue | Severity | Description | Recommendation |
|-------|----------|-------------|----------------|
| TBD | - | Run tests to populate | - |

### 4.2 Security Recommendations

1. **Rate Limiting** - Add rate limiting on `/auth/login` to prevent brute force
2. **Token Refresh** - Consider implementing refresh token flow
3. **HTTPS** - Ensure production uses HTTPS only
4. **CORS** - Review CORS configuration for production

### 4.3 Reliability Recommendations

1. **Health Checks** - Add `/health` endpoint checking all DBs
2. **Timeouts** - Configure database connection timeouts
3. **Circuit Breaker** - Consider circuit breaker for external calls

---

## 5. Test Metrics

### 5.1 Coverage Targets

| Category | Target | Current |
|----------|--------|---------|
| Authentication | 90% | TBD |
| RBAC | 100% | TBD |
| QR Lifecycle | 95% | TBD |
| Transactions | 95% | TBD |
| Overall | 85% | TBD |

### 5.2 Test Counts

| Test File | Tests | Passing | Failing | Skipped |
|-----------|-------|---------|---------|---------|
| test_auth.py | ~15 | TBD | TBD | TBD |
| test_rbac.py | ~20 | TBD | TBD | TBD |
| test_qr_lifecycle.py | ~12 | TBD | TBD | TBD |
| test_student_flows.py | ~8 | TBD | TBD | TBD |
| test_teacher_flows.py | ~10 | TBD | TBD | TBD |
| test_store_flows.py | ~12 | TBD | TBD | TBD |
| test_admin_flows.py | ~16 | TBD | TBD | TBD |
| test_database_consistency.py | ~12 | TBD | TBD | TBD |
| test_failure_modes.py | ~15 | TBD | TBD | TBD |
| test_pwa_compliance.py | ~15 | TBD | TBD | TBD |
| test_frontend_contracts.py | ~10 | TBD | TBD | TBD |

---

## 6. Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| QA Lead | | | |
| Dev Lead | | | |
| Product Owner | | | |

---

*Document Version: 1.0*
*Generated: Phase 1 QA*
