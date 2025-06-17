#!/bin/sh
set -e

# Function to cleanup background processes
cleanup() {
    echo "Cleaning up background processes..."
    # Kill processes with better error handling
    for pid in $MOCK_CASCOIN_PID $MOCK_POLYGON_PID $MAIN_APP_PID $WATCHER_PID; do
        if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
            echo "Killing process $pid"
            kill $pid || echo "Failed to kill process $pid"
        fi
    done

    # Wait a bit and force kill if necessary
    sleep 3
    for pid in $MOCK_CASCOIN_PID $MOCK_POLYGON_PID $MAIN_APP_PID $WATCHER_PID; do
        if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
            echo "Force killing process $pid"
            kill -9 $pid 2>/dev/null || echo "Process $pid already dead"
        fi
    done
    echo "Cleanup complete."
}

# Set trap to cleanup on exit or interrupt
trap cleanup EXIT INT TERM

echo "Initializing database..."
python3 -m backend.init_db

echo "Starting backend services for testing..."

# Start Mock Services in the background
python3 /app/integration_tests/mock_services/mock_cascoin_node.py &
MOCK_CASCOIN_PID=$!
python3 /app/integration_tests/mock_services/mock_polygon_node.py &
MOCK_POLYGON_PID=$!

# Start Main FastAPI Application in the background
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
MAIN_APP_PID=$!

# Start Cascoin Watcher in the background
python3 /app/watchers/cascoin_watcher.py &
WATCHER_PID=$!

echo "Waiting for services to start..."
sleep 15 # Give services time to initialize before running tests

echo "-----------------------------------"
echo "Running Unit Tests (including Fee System and WebSocket Tests)..."
echo "Test directories: /app/tests (unit tests), /app/integration_tests (integration tests)"
echo "-----------------------------------"

# Run unit tests first (including fee system tests)
echo "Running Unit Tests..."
pytest /app/tests -v --tb=short
UNIT_TEST_EXIT_CODE=$?

echo "-----------------------------------"
echo "Running WebSocket Real-time Tests..."
timeout 300 python3 /app/run_websocket_tests.py --verbose
WEBSOCKET_TEST_EXIT_CODE=$?
if [ $WEBSOCKET_TEST_EXIT_CODE -eq 124 ]; then
    echo "⚠️  WebSocket tests timed out after 5 minutes"
    WEBSOCKET_TEST_EXIT_CODE=1
fi

echo "-----------------------------------"
echo "Running Integration Tests..."
pytest /app/integration_tests -v --tb=short
INTEGRATION_TEST_EXIT_CODE=$?

# Calculate overall test result
if [ $UNIT_TEST_EXIT_CODE -eq 0 ] && [ $WEBSOCKET_TEST_EXIT_CODE -eq 0 ] && [ $INTEGRATION_TEST_EXIT_CODE -eq 0 ]; then
    TEST_EXIT_CODE=0
    echo "-----------------------------------"
    echo "✅ ALL TESTS PASSED!"
else
    TEST_EXIT_CODE=1
    echo "-----------------------------------"
    echo "❌ SOME TESTS FAILED"
    echo "Unit tests exit code: $UNIT_TEST_EXIT_CODE"
    echo "WebSocket tests exit code: $WEBSOCKET_TEST_EXIT_CODE"
    echo "Integration tests exit code: $INTEGRATION_TEST_EXIT_CODE"
fi
echo "-----------------------------------"

# Exit with the test exit code (cleanup will be handled by trap)
exit $TEST_EXIT_CODE 