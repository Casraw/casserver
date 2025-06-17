#!/bin/sh
set -e

echo "Initializing database..."
python3 -m backend.init_db

echo "-----------------------------------"
echo "Running Unit Tests Only..."
echo "-----------------------------------"

# Run unit tests only (no services needed for pure unit tests)
echo "Running Unit Tests..."
pytest /app/tests -v --tb=short -x
UNIT_TEST_EXIT_CODE=$?

echo "-----------------------------------"
echo "Running WebSocket Unit Tests Only..."
python3 -m pytest /app/tests/api/test_websocket_api.py /app/tests/services/test_websocket_notifier.py -v --tb=short -x
WEBSOCKET_UNIT_TEST_EXIT_CODE=$?

# Calculate overall test result
if [ $UNIT_TEST_EXIT_CODE -eq 0 ] && [ $WEBSOCKET_UNIT_TEST_EXIT_CODE -eq 0 ]; then
    TEST_EXIT_CODE=0
    echo "-----------------------------------"
    echo "✅ ALL UNIT TESTS PASSED!"
else
    TEST_EXIT_CODE=1
    echo "-----------------------------------"
    echo "❌ SOME UNIT TESTS FAILED"
    echo "Unit tests exit code: $UNIT_TEST_EXIT_CODE"
    echo "WebSocket unit tests exit code: $WEBSOCKET_UNIT_TEST_EXIT_CODE"
fi
echo "-----------------------------------"

# Exit with the test exit code
exit $TEST_EXIT_CODE 