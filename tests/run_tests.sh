#!/bin/bash
# =============================================================================
# QA Test Suite Runner
# =============================================================================
# Runs the complete test suite and generates reports
#
# Usage:
#   ./run_tests.sh           # Run all tests
#   ./run_tests.sh quick     # Run quick tests only
#   ./run_tests.sh auth      # Run auth tests only
#   ./run_tests.sh coverage  # Run with coverage report
# =============================================================================

set -e

cd "$(dirname "$0")/.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "  QA Test Suite Runner"
echo "=============================================="
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"
    if [ -f "../venv/bin/activate" ]; then
        source ../venv/bin/activate
        echo "Activated venv"
    fi
fi

# Install test dependencies
echo "Checking test dependencies..."
pip install pytest pytest-asyncio httpx pytest-cov --quiet 2>/dev/null || true

MODE=${1:-all}

case $MODE in
    quick)
        echo -e "${GREEN}Running quick tests...${NC}"
        pytest tests/test_auth.py tests/test_rbac.py -v --tb=short
        ;;
    
    auth)
        echo -e "${GREEN}Running authentication tests...${NC}"
        pytest tests/test_auth.py -v --tb=long
        ;;
    
    rbac)
        echo -e "${GREEN}Running RBAC tests...${NC}"
        pytest tests/test_rbac.py -v --tb=long
        ;;
    
    qr)
        echo -e "${GREEN}Running QR lifecycle tests...${NC}"
        pytest tests/test_qr_lifecycle.py -v --tb=long
        ;;
    
    flows)
        echo -e "${GREEN}Running flow tests...${NC}"
        pytest tests/test_student_flows.py tests/test_teacher_flows.py tests/test_store_flows.py tests/test_admin_flows.py -v --tb=short
        ;;
    
    db)
        echo -e "${GREEN}Running database consistency tests...${NC}"
        pytest tests/test_database_consistency.py -v --tb=long
        ;;
    
    pwa)
        echo -e "${GREEN}Running PWA compliance tests...${NC}"
        pytest tests/test_pwa_compliance.py -v --tb=short
        ;;
    
    frontend)
        echo -e "${GREEN}Running frontend contract tests...${NC}"
        pytest tests/test_frontend_contracts.py -v --tb=short
        ;;
    
    failure)
        echo -e "${GREEN}Running failure mode tests...${NC}"
        pytest tests/test_failure_modes.py -v --tb=long
        ;;
    
    coverage)
        echo -e "${GREEN}Running all tests with coverage...${NC}"
        pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
        echo ""
        echo -e "${GREEN}Coverage report: htmlcov/index.html${NC}"
        ;;
    
    all)
        echo -e "${GREEN}Running complete test suite...${NC}"
        echo ""
        
        echo "--- Authentication Tests ---"
        pytest tests/test_auth.py -v --tb=short || true
        echo ""
        
        echo "--- RBAC Tests ---"
        pytest tests/test_rbac.py -v --tb=short || true
        echo ""
        
        echo "--- Student Flow Tests ---"
        pytest tests/test_student_flows.py -v --tb=short || true
        echo ""
        
        echo "--- Teacher Flow Tests ---"
        pytest tests/test_teacher_flows.py -v --tb=short || true
        echo ""
        
        echo "--- Store Flow Tests ---"
        pytest tests/test_store_flows.py -v --tb=short || true
        echo ""
        
        echo "--- Admin Flow Tests ---"
        pytest tests/test_admin_flows.py -v --tb=short || true
        echo ""
        
        echo "--- QR Lifecycle Tests ---"
        pytest tests/test_qr_lifecycle.py -v --tb=short || true
        echo ""
        
        echo "--- Database Consistency Tests ---"
        pytest tests/test_database_consistency.py -v --tb=short || true
        echo ""
        
        echo "--- Failure Mode Tests ---"
        pytest tests/test_failure_modes.py -v --tb=short || true
        echo ""
        
        echo "--- PWA Compliance Tests ---"
        pytest tests/test_pwa_compliance.py -v --tb=short || true
        echo ""
        
        echo "--- Frontend Contract Tests ---"
        pytest tests/test_frontend_contracts.py -v --tb=short || true
        ;;
    
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: ./run_tests.sh [quick|auth|rbac|qr|flows|db|pwa|frontend|failure|coverage|all]"
        exit 1
        ;;
esac

echo ""
echo "=============================================="
echo "  Test Run Complete"
echo "=============================================="
