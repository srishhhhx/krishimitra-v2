#!/bin/bash
# Test runner script for Krishi Mitra backend

set -e  # Exit on error

echo "🧪 Krishi Mitra Backend Test Suite"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "Activating venv..."
    source venv/bin/activate
fi

# Install test dependencies
echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
pip install -q -r requirements-test.txt

echo ""
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Run different test suites based on argument
case "${1:-all}" in
    unit)
        echo "🔬 Running Unit Tests..."
        pytest tests/unit/ -v --cov=services --cov=core --cov-report=term-missing
        ;;
    integration)
        echo "🔗 Running Integration Tests..."
        pytest tests/integration/ -v --cov=routers --cov-report=term-missing
        ;;
    coverage)
        echo "📊 Running Tests with Full Coverage Report..."
        pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing
        echo ""
        echo -e "${GREEN}📊 Coverage report generated in htmlcov/index.html${NC}"
        ;;
    fast)
        echo "⚡ Running Fast Tests (excluding slow tests)..."
        pytest tests/ -v -m "not slow"
        ;;
    auth)
        echo "🔐 Running Authentication Tests..."
        pytest tests/ -v -m auth
        ;;
    rag)
        echo "🤖 Running RAG Tests..."
        pytest tests/ -v -m rag
        ;;
    all)
        echo "🚀 Running All Tests..."
        pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html
        echo ""
        echo -e "${GREEN}✅ All tests completed${NC}"
        echo -e "${GREEN}📊 Coverage report: htmlcov/index.html${NC}"
        ;;
    *)
        echo -e "${RED}❌ Unknown test suite: $1${NC}"
        echo "Usage: ./run_tests.sh [unit|integration|coverage|fast|auth|rag|all]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✨ Testing complete!${NC}"
