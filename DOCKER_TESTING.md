# Docker Testing Guide

This document explains how tests are run in the Docker environment, including the comprehensive fee system tests.

## Test Structure in Docker

The Docker container runs two types of tests:

### 1. Unit Tests (`/app/tests/`)
- **Fee System Tests**: Complete test suite for fee calculations and API endpoints
  - `tests/services/test_fee_service.py` - FeeService unit tests
  - `tests/services/test_matic_fee_service.py` - MaticFeeService unit tests  
  - `tests/api/test_fee_routes.py` - Fee API endpoint tests
- **Other Service Tests**: Existing service layer tests
- **Database Tests**: Model and CRUD operation tests

### 2. Integration Tests (`/app/integration_tests/`)
- End-to-end bridge functionality tests
- Mock service integration tests
- Full workflow validation tests

## Running Tests in Docker

### Build and Run All Tests
```bash
docker build -t casserver-test .
docker run --rm casserver-test
```

### Run Only Fee System Tests
```bash
docker run --rm casserver-test /app/test_fee_system_docker.sh
```

### Interactive Testing
```bash
docker run -it --rm casserver-test /bin/bash
# Inside container:
pytest /app/tests/services/test_fee_service.py -v
pytest /app/tests/services/test_matic_fee_service.py -v
pytest /app/tests/api/test_fee_routes.py -v
```

## Test Environment Configuration

The Docker container sets up the following environment variables for testing:

### Core Configuration
- `PYTHONPATH=/app` - Python module path
- `FLASK_ENV=development` - Development mode
- `SKIP_INTEGRATION_TESTS=false` - Run integration tests

### Fee System Configuration
- `DIRECT_PAYMENT_FEE_PERCENTAGE=0.1` - 0.1% fee for direct MATIC payment
- `DEDUCTED_FEE_PERCENTAGE=2.5` - 2.5% fee for deducted model
- `MINIMUM_BRIDGE_AMOUNT=1.0` - Minimum bridge amount
- `MATIC_TO_CAS_EXCHANGE_RATE=100.0` - Exchange rate (1 MATIC = 100 CAS)
- `MATIC_TO_WCAS_EXCHANGE_RATE=100.0` - Exchange rate (1 MATIC = 100 wCAS)
- `GAS_PRICE_GWEI=30.0` - Gas price in Gwei
- `GAS_PRICE_BUFFER_PERCENTAGE=20.0` - Gas price buffer (20%)
- `TOKEN_CONVERSION_FEE_PERCENTAGE=0.5` - Token conversion fee (0.5%)

### Mock Services Configuration
- `POLYGON_RPC_URL=http://localhost:5002` - Mock Polygon node
- `CASCOIN_RPC_URL=http://localhost:5001` - Mock CAS node
- `BRIDGE_API_URL=http://localhost:8000/internal` - Bridge API endpoint

## Test Execution Flow

1. **Service Startup**: Mock services and main application start
2. **Unit Tests**: All unit tests run first (including fee system)
3. **Integration Tests**: Full integration tests run second
4. **Cleanup**: All background services are terminated
5. **Exit**: Container exits with test result code

## Test Output

The Docker container provides detailed test output:

```
Running Unit Tests (including Fee System Tests)...
Test directories: /app/tests (unit tests), /app/integration_tests (integration tests)
-----------------------------------

Running Unit Tests...
tests/services/test_fee_service.py::TestFeeService::test_init_successful PASSED
tests/services/test_fee_service.py::TestFeeService::test_calculate_direct_payment_fees_cas_to_wcas PASSED
...
tests/api/test_fee_routes.py::TestFeeRoutes::test_estimate_fees_direct_payment_success PASSED
...

-----------------------------------
Running Integration Tests...
...

-----------------------------------
✅ ALL TESTS PASSED!
-----------------------------------
```

## Fee System Test Coverage

The fee system tests provide comprehensive coverage:

### FeeService Tests (30+ tests)
- ✅ Service initialization and configuration
- ✅ Direct payment fee calculations
- ✅ Deducted fee calculations  
- ✅ Input validation (amounts, operations, fee models)
- ✅ Error handling and edge cases
- ✅ Precision handling for financial calculations

### MaticFeeService Tests (35+ tests)
- ✅ Gas estimation for mint/burn operations
- ✅ MATIC ↔ Token conversions with fees
- ✅ Exchange rate management
- ✅ Configuration handling
- ✅ Edge cases (very small/large amounts)

### Fee API Tests (15+ tests)
- ✅ All fee estimation endpoints
- ✅ MATIC payment options
- ✅ Exchange rate retrieval
- ✅ Request validation and error responses
- ✅ Address format validation

## Continuous Integration

The Docker-based testing is designed for CI/CD:

- **Deterministic**: Same results every run
- **Isolated**: No external dependencies
- **Fast**: Optimized for quick feedback
- **Comprehensive**: Full system coverage

## Troubleshooting

### Common Issues

1. **Test Failures**: Check test output for specific failure details
2. **Service Startup**: Ensure mock services start properly (15s wait time)
3. **Environment**: Verify all required environment variables are set
4. **Dependencies**: Ensure all Python packages are installed

### Debug Mode

For detailed debugging:
```bash
docker run -it --rm casserver-test /bin/bash
export PYTHONPATH=/app
pytest /app/tests -v -s --tb=long
```

### Fee System Only

To test only fee system components:
```bash
docker run --rm casserver-test /app/test_fee_system_docker.sh
```

This will run only the fee-related tests with detailed output and summary. 