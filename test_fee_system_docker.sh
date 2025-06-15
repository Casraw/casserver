#!/bin/bash
# Test script specifically for fee system components in Docker environment

echo "=========================================="
echo "Running Fee System Integration Tests"
echo "=========================================="

# Set environment variables for testing
export PYTHONPATH=/app
export DATABASE_URL="sqlite:////app/test_fee_system.db"

# Run only the integration test that actually works with the real services
echo "Running fee system integration tests..."
python -m pytest tests/integration/test_fee_system_integration.py -v

# Check if tests passed
if [ $? -eq 0 ]; then
    echo "✅ Fee system integration tests PASSED"
    exit 0
else
    echo "❌ Fee system integration tests FAILED"
    exit 1
fi 