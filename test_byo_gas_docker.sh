#!/bin/bash
# Test script for BYO-gas (Bring Your Own Gas) functionality in Docker environment

echo "=========================================="
echo "Running BYO-gas Integration Tests"
echo "=========================================="

# Set environment variables for testing
export PYTHONPATH=/app
export DATABASE_URL="sqlite:////app/test_byo_gas.db"
export HD_MNEMONIC="abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
export INTERNAL_API_KEY="test_internal_key_byo_gas"
export POLYGON_RPC_URL="https://polygon-rpc.com"
export WCAS_CONTRACT_ADDRESS="0x1234567890123456789012345678901234567890"
export MINTER_PRIVATE_KEY="0x1111111111111111111111111111111111111111111111111111111111111111"

# Clean up any existing test database
rm -f /app/test_byo_gas.db

echo "=========================================="
echo "1. Running CRUD Tests for BYO-gas"
echo "=========================================="
python -m pytest tests/test_crud_byo_gas.py -v

if [ $? -ne 0 ]; then
    echo "❌ BYO-gas CRUD tests FAILED"
    exit 1
fi

echo "=========================================="
echo "2. Running API Tests for BYO-gas"
echo "=========================================="
python -m pytest tests/api/test_internal_api.py::TestInternalAPIBYOGas -v

if [ $? -ne 0 ]; then
    echo "❌ BYO-gas API tests FAILED"
    exit 1
fi

echo "=========================================="
echo "3. Running Service Tests for BYO-gas"
echo "=========================================="
python -m pytest tests/services/test_polygon_service_byo_gas.py -v

if [ $? -ne 0 ]; then
    echo "❌ BYO-gas service tests FAILED"
    exit 1
fi

echo "=========================================="
echo "4. Running Integration Tests for BYO-gas"
echo "=========================================="
python -m pytest tests/integration/test_byo_gas_integration.py -v

if [ $? -ne 0 ]; then
    echo "❌ BYO-gas integration tests FAILED"
    exit 1
fi

echo "=========================================="
echo "5. Running Migration Tests"
echo "=========================================="
python -m pytest tests/test_migrations.py -v -k "polygon_gas"

if [ $? -ne 0 ]; then
    echo "❌ BYO-gas migration tests FAILED"
    exit 1
fi

echo "=========================================="
echo "6. Testing HD Wallet Generation"
echo "=========================================="
python -c "
import os
os.environ['HD_MNEMONIC'] = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
from backend.services.polygon_service import generate_hd_address
try:
    address, private_key, index = generate_hd_address()
    print(f'✅ HD Address generation successful:')
    print(f'   Address: {address}')
    print(f'   Index: {index}')
    print(f'   Private key length: {len(private_key)} chars')
    assert address.startswith('0x'), 'Address should start with 0x'
    assert len(address) == 42, 'Address should be 42 characters'
    assert private_key.startswith('0x'), 'Private key should start with 0x'
    assert len(private_key) == 66, 'Private key should be 66 characters'
    assert isinstance(index, int), 'Index should be integer'
    print('✅ All HD wallet validations passed')
except Exception as e:
    print(f'❌ HD wallet generation failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ HD wallet generation test FAILED"
    exit 1
fi

echo "=========================================="
echo "7. Testing Database Migration"
echo "=========================================="
python -c "
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.migrations import run_polygon_gas_deposits_migration

# Create test database
engine = create_engine('sqlite:////app/test_migration_byo_gas.db')
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    run_polygon_gas_deposits_migration(db)
    print('✅ Database migration successful')
    
    # Verify table was created
    result = db.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"polygon_gas_deposits\"')
    if result.fetchone():
        print('✅ polygon_gas_deposits table created successfully')
    else:
        print('❌ polygon_gas_deposits table not found')
        exit(1)
        
except Exception as e:
    print(f'❌ Database migration failed: {e}')
    exit(1)
finally:
    db.close()
"

if [ $? -ne 0 ]; then
    echo "❌ Database migration test FAILED"
    exit 1
fi

# Clean up test databases
rm -f /app/test_byo_gas.db
rm -f /app/test_migration_byo_gas.db

echo "=========================================="
echo "✅ ALL BYO-GAS TESTS PASSED!"
echo "=========================================="
echo ""
echo "Test Summary:"
echo "✅ CRUD operations for gas deposits"
echo "✅ API endpoints for gas address requests"
echo "✅ Polygon service with custom private keys"
echo "✅ Complete integration flow"
echo "✅ Database migration system"
echo "✅ HD wallet address generation"
echo ""
echo "🎉 BYO-gas feature is ready for production!"

exit 0 