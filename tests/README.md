# Fee System Test Suite

This directory contains comprehensive unit tests for the fee system components of the CAS bridge.

## Test Structure

```
tests/
├── services/
│   ├── test_fee_service.py          # Tests for FeeService class
│   ├── test_matic_fee_service.py    # Tests for MaticFeeService class
│   ├── test_websocket_notifier.py   # Tests for WebSocket notification service
│   └── __init__.py
├── api/
│   ├── test_fee_routes.py           # Tests for fee API endpoints
│   ├── test_internal_api.py         # Tests for internal API endpoints
│   ├── test_websocket_api.py        # Tests for WebSocket API endpoints
│   └── __init__.py
├── __init__.py
└── README.md
```

## Integration Tests

```
integration_tests/
├── test_realtime_websocket_integration.py    # Real-time WebSocket integration tests
├── test_integration_cas_to_wcas.py           # CAS to wCAS bridge tests
├── test_integration_wcas_to_cas.py           # wCAS to CAS bridge tests
├── test_watcher_resilience.py               # Watcher resilience tests
└── mock_services/                            # Mock service implementations
```

## Test Coverage

### Fee System Tests

#### FeeService Tests (`test_fee_service.py`)
- **Initialization**: Service setup and configuration loading
- **Direct Payment Fees**: Fee calculations for direct MATIC payment model
- **Deducted Fees**: Fee calculations for all-inclusive deducted model
- **Validation**: Amount, operation, and fee model validation
- **Error Handling**: Exception handling and error messages
- **Edge Cases**: Small amounts, large amounts, precision handling
- **Integration**: MATIC service integration and error handling

#### MaticFeeService Tests (`test_matic_fee_service.py`)
- **Gas Estimation**: Gas cost calculations for mint/burn operations
- **Token Conversion**: MATIC ↔ CAS/wCAS conversion calculations
- **Exchange Rates**: Rate management and retrieval
- **Fee Calculations**: Complete MATIC fee calculations
- **Precision Handling**: Small and large amount calculations
- **Configuration**: Gas price, buffer, and conversion fee settings
- **Error Handling**: Invalid inputs and edge cases

#### Fee API Tests (`test_fee_routes.py`)
- **Fee Estimation Endpoint**: `/api/fees/estimate` testing
- **Quick Estimation**: `/api/fees/quick-estimate` testing
- **MATIC Options**: `/api/fees/matic-options/{address}` testing
- **Token Conversion**: `/api/fees/calculate-token-to-matic` testing
- **Exchange Rates**: `/api/fees/exchange-rates` testing
- **Configuration**: `/api/fees/config` testing
- **Request Validation**: Input validation and error responses
- **Address Validation**: Ethereum address format validation

### Real-time WebSocket Tests

#### WebSocket API Tests (`test_websocket_api.py`)
- **Connection Manager**: WebSocket connection lifecycle management
- **User Isolation**: Ensuring users only receive their own updates
- **Message Handling**: Ping/pong, status requests, error handling
- **Notification Functions**: CAS deposit, wCAS return intention, and transaction updates
- **Error Handling**: Connection failures, invalid JSON, logging
- **Endpoint Testing**: WebSocket endpoint functionality and validation

#### WebSocket Notifier Service Tests (`test_websocket_notifier.py`)
- **Service Initialization**: Event loop management and service setup
- **Notification Scheduling**: Running vs non-running event loop handling
- **Async Integration**: Async function calling and error handling
- **Global Instance**: Testing the global notifier instance
- **Full Notification Cycle**: Complete notification flow testing
- **Error Resilience**: Exception handling and logging

#### WebSocket Integration Tests (`test_realtime_websocket_integration.py`)
- **Complete Lifecycle Testing**: Full CAS deposit and wCAS return intention flows
- **Real-time Updates**: Status change propagation and UI update simulation
- **User Isolation**: Multi-user scenario testing
- **Connection Management**: Connection establishment, ping/pong, disconnection
- **Data Consistency**: Initial state loading and incremental updates
- **Stress Testing**: Multiple concurrent connections and rapid updates
- **Error Scenarios**: Invalid JSON, connection failures, data corruption

### Internal API Tests (`test_internal_api.py`)
- **API Key Authentication**: Security validation and access control
- **Minting Operations**: wCAS minting process and validation
- **Releasing Operations**: CAS release process and validation
- **Error Handling**: Various failure scenarios and error responses
- **Data Validation**: Request format and data integrity checks

## Running Tests

### Run All Tests
```bash
# All tests including WebSocket tests
pytest tests/ integration_tests/ -v

# With coverage
pytest tests/ integration_tests/ --cov=backend --cov-report=html
```

### Run Specific Test Categories

#### Fee System Tests
```bash
python run_fee_tests.py
python run_fee_tests.py --coverage
```

#### WebSocket Real-time Tests
```bash
python run_websocket_tests.py
python run_websocket_tests.py --coverage
python run_websocket_tests.py --unit          # Unit tests only
python run_websocket_tests.py --integration   # Integration tests only
```

#### Run by Test Markers
```bash
# WebSocket tests only
pytest -m websocket -v

# Real-time functionality tests
pytest -m realtime -v

# Unit tests only
pytest -m unit -v

# Integration tests only
pytest -m integration -v

# API endpoint tests
pytest -m api -v

# Service layer tests
pytest -m services -v

# Fee system tests
pytest -m fee_system -v
```

### Run Specific Test Modules
```bash
python -m pytest tests/api/test_websocket_api.py -v
python -m pytest tests/services/test_websocket_notifier.py -v
python -m pytest integration_tests/test_realtime_websocket_integration.py -v
```

### Docker Integration
```bash
# Run all tests in Docker environment
docker build -t bridge-test .
docker run bridge-test

# Run specific test category in Docker
docker run bridge-test python run_websocket_tests.py --verbose
```

## Test Features

### Mocking Strategy
- **Settings**: All configuration values are mocked for consistent testing
- **Services**: External service dependencies are mocked
- **API Clients**: HTTP clients and external APIs are mocked
- **Database**: In-memory SQLite databases for integration tests
- **WebSocket Connections**: Mocked WebSocket instances for unit tests
- **Event Loops**: Async event loop management and testing

### Test Data
- **Realistic Values**: Test data reflects real-world usage scenarios
- **Edge Cases**: Boundary conditions and extreme values
- **Error Conditions**: Invalid inputs and failure scenarios
- **Precision**: Decimal precision and rounding behavior
- **Concurrent Scenarios**: Multi-user and multi-connection testing
- **State Transitions**: Complete lifecycle and status change testing

### Assertions
- **Exact Values**: Precise numerical comparisons where appropriate
- **Approximate Values**: Floating-point comparisons with tolerance
- **Structure Validation**: Response format and field presence
- **Error Messages**: Specific error message content validation
- **Async Behavior**: Proper async function execution and timing
- **State Changes**: Database state and real-time update verification

## Test Configuration

### Environment Variables
Tests use mocked settings and don't require environment configuration for most scenarios.

### Dependencies
- `unittest`: Python standard testing framework
- `unittest.mock`: Mocking framework for isolating components
- `fastapi.testclient`: API endpoint testing
- `pytest` (optional): Alternative test runner with additional features
- `pytest-asyncio`: Async test support
- `pytest-cov`: Coverage reporting
- `websockets`: WebSocket client library for integration tests

### Mock Settings
Default mock values used in tests:
- `DIRECT_PAYMENT_FEE_PERCENTAGE`: 0.1% (0.1)
- `DEDUCTED_FEE_PERCENTAGE`: 2.5% (2.5)
- `MINIMUM_BRIDGE_AMOUNT`: 1.0
- `MATIC_TO_CAS_EXCHANGE_RATE`: 100.0
- `MATIC_TO_WCAS_EXCHANGE_RATE`: 100.0
- `GAS_PRICE_GWEI`: 30.0
- `GAS_PRICE_BUFFER_PERCENTAGE`: 20.0
- `TOKEN_CONVERSION_FEE_PERCENTAGE`: 0.5

## Real-time Testing Considerations

### WebSocket Testing Challenges
- **Async Nature**: All WebSocket operations are asynchronous
- **Connection Lifecycle**: Proper setup and teardown of connections
- **Message Ordering**: Ensuring correct order of real-time updates
- **Concurrency**: Testing multiple simultaneous connections
- **Error Recovery**: Connection failures and reconnection scenarios

### Integration Test Database
- **In-memory SQLite**: Fast, isolated database for each test
- **State Management**: Proper cleanup between tests
- **Transaction Handling**: Ensuring ACID properties during testing
- **Real-time Notifications**: Testing actual database triggers

### Performance Considerations
- **Connection Limits**: Testing with multiple concurrent connections
- **Message Throughput**: Rapid status update scenarios
- **Memory Usage**: Long-running connection testing
- **Cleanup**: Proper resource cleanup to prevent test interference

## Adding New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<functionality>_<scenario>`

### Test Structure
```python
@pytest.mark.unit  # or @pytest.mark.integration
@pytest.mark.websocket  # for WebSocket-related tests
@pytest.mark.realtime   # for real-time functionality tests
class TestClassName(unittest.TestCase):
    def test_functionality_scenario(self):
        """Test description explaining what is being tested."""
        # Arrange: Set up test data and mocks
        # Act: Execute the functionality being tested
        # Assert: Verify the expected results
```

### Mock Setup for Async Tests
```python
def setUp(self):
    """Set up test fixtures before each test method."""
    # Create mocks
    self.mock_manager = AsyncMock()
    # Patch dependencies
    self.patcher = patch('module.dependency', self.mock_manager)
    self.patcher.start()

def tearDown(self):
    """Clean up after each test method."""
    # Stop patches
    self.patcher.stop()
```

### WebSocket Test Patterns
```python
def test_websocket_functionality(self):
    """Test WebSocket endpoint functionality."""
    with self.client.websocket_connect(f"/api/ws/{user_address}") as websocket:
        # Send test message
        websocket.send_text(json.dumps({"type": "ping"}))
        
        # Receive and validate response
        response = websocket.receive_text()
        data = json.loads(response)
        
        self.assertEqual(data["type"], "pong")
```

## Continuous Integration

These tests are designed to run in CI/CD environments:
- No external dependencies for unit tests
- Deterministic results with mocked dependencies
- Fast execution with proper async handling
- Clear failure reporting with detailed error messages
- Isolated test environments with proper cleanup

## Troubleshooting

### Common Issues

#### WebSocket Test Issues
1. **Connection Timeouts**: Increase timeout values in test configuration
2. **Async Test Failures**: Ensure proper await/async syntax
3. **Database State Issues**: Verify proper cleanup between tests
4. **Mock Configuration**: Check async mock setup and patching

#### General Test Issues
1. **Import Errors**: Ensure `PYTHONPATH` includes project root
2. **Mock Failures**: Verify mock patch paths match actual imports
3. **Assertion Errors**: Check expected vs actual values in test output
4. **Timeout Issues**: Tests should complete quickly; check for infinite loops

### Debug Mode
Run tests with verbose output:
```bash
python -m pytest tests/ -v -s --tb=long
python run_websocket_tests.py --verbose
```

### WebSocket Debug
Enable WebSocket debug logging:
```python
import logging
logging.getLogger('websockets').setLevel(logging.DEBUG)
```

### Test Isolation
Each test method is isolated:
- Fresh mocks for each test
- Clean database state
- Independent WebSocket connections
- No shared state between tests

### Performance Debugging
Profile test execution:
```bash
python -m pytest tests/ --profile-svg
python -m pytest tests/ --durations=10
``` 