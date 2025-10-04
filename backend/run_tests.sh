#!/bin/bash
# Comprehensive test runner script for Sales Agent backend

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Sales Agent - Test Suite Runner${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

# Default values
RUN_UNIT=true
RUN_INTEGRATION=false
RUN_E2E=false
RUN_LOAD=false
RUN_COVERAGE=true
RUN_LINT=false
PARALLEL=false
VERBOSE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            RUN_UNIT=true
            RUN_INTEGRATION=true
            RUN_E2E=true
            shift
            ;;
        --unit)
            RUN_UNIT=true
            RUN_INTEGRATION=false
            RUN_E2E=false
            shift
            ;;
        --integration)
            RUN_INTEGRATION=true
            shift
            ;;
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --load)
            RUN_LOAD=true
            shift
            ;;
        --no-coverage)
            RUN_COVERAGE=false
            shift
            ;;
        --lint)
            RUN_LINT=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: ./run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  --all           Run all tests (unit, integration, e2e)"
            echo "  --unit          Run only unit tests (default)"
            echo "  --integration   Include integration tests"
            echo "  --e2e           Include E2E tests"
            echo "  --load          Run load tests with Locust"
            echo "  --no-coverage   Skip coverage reporting"
            echo "  --lint          Run linters and formatters"
            echo "  --parallel      Run tests in parallel"
            echo "  --verbose       Verbose output"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠️  Warning: No virtual environment detected${NC}"
    echo -e "${YELLOW}   Consider activating venv: source venv/bin/activate${NC}\n"
fi

# Install test dependencies if needed
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
    pip install -r requirements-test.txt
    echo ""
fi

# Linting and formatting
if [ "$RUN_LINT" = true ]; then
    echo -e "${BLUE}🔍 Running code quality checks...${NC}"
    
    echo -e "${YELLOW}  Running Ruff linter...${NC}"
    ruff check app/ tests/ || true
    
    echo -e "${YELLOW}  Running Black formatter check...${NC}"
    black --check app/ tests/ || true
    
    echo -e "${YELLOW}  Running MyPy type checking...${NC}"
    mypy app/ --ignore-missing-imports || true
    
    echo -e "${YELLOW}  Running isort import sorting check...${NC}"
    isort --check-only app/ tests/ || true
    
    echo -e "${YELLOW}  Running Bandit security check...${NC}"
    bandit -r app/ -ll || true
    
    echo ""
fi

# Build pytest command
PYTEST_CMD="pytest"
PYTEST_ARGS=""

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -vv"
else
    PYTEST_ARGS="$PYTEST_ARGS -v"
fi

if [ "$PARALLEL" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -n auto"
fi

if [ "$RUN_COVERAGE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml"
fi

# Run unit tests
if [ "$RUN_UNIT" = true ]; then
    echo -e "${BLUE}🧪 Running unit tests...${NC}"
    $PYTEST_CMD tests/ -m "not integration and not e2e" $PYTEST_ARGS
    UNIT_EXIT=$?
    echo ""
fi

# Run integration tests
if [ "$RUN_INTEGRATION" = true ]; then
    echo -e "${BLUE}🔗 Running integration tests...${NC}"
    echo -e "${YELLOW}  Note: Requires PostgreSQL and Redis running${NC}"
    $PYTEST_CMD tests/ -m "integration" $PYTEST_ARGS --run-integration
    INTEGRATION_EXIT=$?
    echo ""
fi

# Run E2E tests
if [ "$RUN_E2E" = true ]; then
    echo -e "${BLUE}🌐 Running E2E tests...${NC}"
    echo -e "${YELLOW}  Note: Requires full system running${NC}"
    cd ../frontend
    npx playwright test
    E2E_EXIT=$?
    cd ../backend
    echo ""
fi

# Run load tests
if [ "$RUN_LOAD" = true ]; then
    echo -e "${BLUE}⚡ Running load tests...${NC}"
    echo -e "${YELLOW}  Starting Locust in headless mode...${NC}"
    locust -f tests/load_tests.py \
        --host=http://localhost:8001 \
        --users=100 \
        --spawn-rate=10 \
        --run-time=60s \
        --headless \
        --csv=test-results/load-test
    LOAD_EXIT=$?
    echo ""
fi

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Results Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

if [ "$RUN_UNIT" = true ]; then
    if [ ${UNIT_EXIT:-0} -eq 0 ]; then
        echo -e "${GREEN}✅ Unit tests: PASSED${NC}"
    else
        echo -e "${RED}❌ Unit tests: FAILED${NC}"
    fi
fi

if [ "$RUN_INTEGRATION" = true ]; then
    if [ ${INTEGRATION_EXIT:-0} -eq 0 ]; then
        echo -e "${GREEN}✅ Integration tests: PASSED${NC}"
    else
        echo -e "${RED}❌ Integration tests: FAILED${NC}"
    fi
fi

if [ "$RUN_E2E" = true ]; then
    if [ ${E2E_EXIT:-0} -eq 0 ]; then
        echo -e "${GREEN}✅ E2E tests: PASSED${NC}"
    else
        echo -e "${RED}❌ E2E tests: FAILED${NC}"
    fi
fi

if [ "$RUN_LOAD" = true ]; then
    if [ ${LOAD_EXIT:-0} -eq 0 ]; then
        echo -e "${GREEN}✅ Load tests: PASSED${NC}"
    else
        echo -e "${RED}❌ Load tests: FAILED${NC}"
    fi
fi

if [ "$RUN_COVERAGE" = true ] && [ "$RUN_UNIT" = true ]; then
    echo -e "\n${BLUE}📊 Coverage Report:${NC}"
    echo -e "${YELLOW}   HTML report: backend/htmlcov/index.html${NC}"
    echo -e "${YELLOW}   XML report: backend/coverage.xml${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

# Exit with failure if any tests failed
if [ ${UNIT_EXIT:-0} -ne 0 ] || [ ${INTEGRATION_EXIT:-0} -ne 0 ] || [ ${E2E_EXIT:-0} -ne 0 ] || [ ${LOAD_EXIT:-0} -ne 0 ]; then
    exit 1
fi

echo -e "${GREEN}🎉 All tests passed!${NC}\n"
exit 0
