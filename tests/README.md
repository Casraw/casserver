# Fee System Test Suite

This directory contains comprehensive unit tests for the fee system components of the CAS bridge.

## Test Structure

```
tests/
├── services/
│   ├── test_fee_service.py          # Tests for FeeService class
│   ├── test_matic_fee_service.py    # Tests for MaticFeeService class
│   └── __init__.py
├── api/
│   ├── test_fee_routes.py           # Tests for fee API endpoints
│   └── __init__.py
├── __init__.py
└── README.md
```

## Test Coverage

### FeeService Tests (`test_fee_service.py`)
- **Initialization**: Service setup and configuration loading
- **Direct Payment Fees**: Fee calculations for direct MATIC payment model
- **Deducted Fees**: Fee calculations for all-inclusive deducted model
- **Validation**: Amount, operation, and fee model validation
- **Error Handling**: Exception handling and error messages
- **Edge Cases**: Small amounts, large amounts, precision handling
- **Integration**: MATIC service integration and error handling

### MaticFeeService Tests (`test_matic_fee_service.py`)
- **Gas Estimation**: Gas cost calculations for mint/burn operations
- **Token Conversion**: MATIC ↔ CAS/wCAS conversion calculations
- **Exchange Rates**: Rate management and retrieval
- **Fee Calculations**: Complete MATIC fee calculations
- **Precision Handling**: Small and large amount calculations
- **Configuration**: Gas price, buffer, and conversion fee settings
- **Error Handling**: Invalid inputs and edge cases

### Fee API Tests (`test_fee_routes.py`)
- **Fee Estimation Endpoint**: `/api/fees/estimate` testing
- **Quick Estimation**: `/api/fees/quick-estimate` testing
- **MATIC Options**: `/api/fees/matic-options/{address}` testing
- **Token Conversion**: `/api/fees/calculate-token-to-matic` testing
- **Exchange Rates**: `/api/fees/exchange-rates` testing
- **Configuration**: `/api/fees/config` testing
- **Request Validation**: Input validation and error responses
- **Address Validation**: Ethereum address format validation

## Running Tests

### Run All Fee Tests
```bash
python run_fee_tests.py
```

### Run Specific Test Module
```bash
python -m pytest tests/services/test_fee_service.py -v
python -m pytest tests/services/test_matic_fee_service.py -v
python -m pytest tests/api/test_fee_routes.py -v
```

### Run Specific Test Class
```bash
python run_fee_tests.py tests.services.test_fee_service.TestFeeService
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=backend.services.fee_service --cov=backend.services.matic_fee_service --cov=backend.api.fee_routes --cov-report=html
```

## Test Features

### Mocking Strategy
- **Settings**: All configuration values are mocked for consistent testing
- **Services**: External service dependencies are mocked
- **API Clients**: HTTP clients and external APIs are mocked
- **Database**: No database dependencies in fee system tests

### Test Data
- **Realistic Values**: Test data reflects real-world usage scenarios
- **Edge Cases**: Boundary conditions and extreme values
- **Error Conditions**: Invalid inputs and failure scenarios
- **Precision**: Decimal precision and rounding behavior

### Assertions
- **Exact Values**: Precise numerical comparisons where appropriate
- **Approximate Values**: Floating-point comparisons with tolerance
- **Structure Validation**: Response format and field presence
- **Error Messages**: Specific error message content validation

## Test Configuration

### Environment Variables
Tests use mocked settings and don't require environment configuration.

### Dependencies
- `unittest`: Python standard testing framework
- `unittest.mock`: Mocking framework for isolating components
- `fastapi.testclient`: API endpoint testing
- `pytest` (optional): Alternative test runner with additional features

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

## Adding New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<functionality>_<scenario>`

### Test Structure
```python
def test_functionality_scenario(self):
    """Test description explaining what is being tested."""
    # Arrange: Set up test data and mocks
    # Act: Execute the functionality being tested
    # Assert: Verify the expected results
```

### Mock Setup
```python
def setUp(self):
    """Set up test fixtures before each test method."""
    # Create mocks
    # Patch dependencies
    # Initialize test objects

def tearDown(self):
    """Clean up after each test method."""
    # Stop patches
    # Clean up resources
```

## Continuous Integration

These tests are designed to run in CI/CD environments:
- No external dependencies
- Deterministic results
- Fast execution
- Clear failure reporting

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure `PYTHONPATH` includes project root
2. **Mock Failures**: Verify mock patch paths match actual imports
3. **Assertion Errors**: Check expected vs actual values in test output
4. **Timeout Issues**: Tests should complete quickly; check for infinite loops

### Debug Mode
Run tests with verbose output:
```bash
python -m pytest tests/ -v -s
```

### Test Isolation
Each test method is isolated:
- Fresh mocks for each test
- No shared state between tests
- Independent setup and teardown 