#!/usr/bin/env python3
"""
Simple test script for BYO-gas functionality
"""
import os
import sys
import tempfile
from decimal import Decimal

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

def test_schemas():
    """Test that schemas import correctly"""
    try:
        from backend.schemas import (
            PolygonGasAddressRequest, 
            PolygonGasAddressResponse,
            PolygonGasDepositCreate
        )
        print("✅ Schemas import successfully")
        
        # Test schema creation
        request = PolygonGasAddressRequest(
            cas_deposit_id=1,
            required_matic=0.005
        )
        print(f"✅ Schema creation successful: {request}")
        return True
    except Exception as e:
        print(f"❌ Schema test failed: {e}")
        return False

def test_hd_wallet():
    """Test HD wallet generation"""
    try:
        # Set test mnemonic
        os.environ['HD_MNEMONIC'] = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
        
        # Install required dependencies if not available
        try:
            from backend.services.polygon_service import generate_hd_address
        except ImportError as import_error:
            print(f"❌ Missing dependencies: {import_error}")
            print("   Please install: pip install mnemonic hdwallet")
            return False
        
        address, private_key, index = generate_hd_address()
        
        # Validate results
        assert address.startswith('0x'), f"Address should start with 0x, got {address}"
        assert len(address) == 42, f"Address should be 42 chars, got {len(address)}"
        assert private_key.startswith('0x'), f"Private key should start with 0x, got {private_key}"
        assert len(private_key) == 66, f"Private key should be 66 chars, got {len(private_key)}"
        assert isinstance(index, int), f"Index should be int, got {type(index)}"
        
        print(f"✅ HD wallet generation successful:")
        print(f"   Address: {address}")
        print(f"   Index: {index}")
        print(f"   Private key length: {len(private_key)} chars")
        return True
    except Exception as e:
        print(f"❌ HD wallet test failed: {e}")
        return False

def test_database_migration():
    """Test database migration"""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.migrations import run_polygon_gas_deposits_migration
        import time
        
        # Create temporary database with unique name
        db_path = f"test_migration_{int(time.time_ns())}.db"
        
        try:
            engine = create_engine(f'sqlite:///{db_path}')
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            # Run migration
            run_polygon_gas_deposits_migration(db)
            
            # Verify table was created
            from sqlalchemy import text
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='polygon_gas_deposits'"))
            if result.fetchone():
                print("✅ Database migration successful - polygon_gas_deposits table created")
                return True
            else:
                print("❌ Database migration failed - table not found")
                return False
                
        finally:
            try:
                db.close()
                if os.path.exists(db_path):
                    os.unlink(db_path)
            except:
                pass  # Ignore cleanup errors
            
    except Exception as e:
        print(f"❌ Database migration test failed: {e}")
        return False

def test_crud_operations():
    """Test CRUD operations for gas deposits"""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base, PolygonGasDeposit
        from backend.schemas import PolygonGasDepositCreate
        from backend import crud
        import time
        
        # Create temporary database with unique name
        db_path = f"test_crud_{int(time.time_ns())}.db"
        
        try:
            engine = create_engine(f'sqlite:///{db_path}')
            Base.metadata.create_all(bind=engine)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            # Mock HD address generation for this test
            from backend.services.polygon_service import generate_hd_address
            from backend.services import polygon_service
            
            original_generate = polygon_service.generate_hd_address
            def mock_generate_hd_address(index=None):
                return (
                    "0x1234567890123456789012345678901234567890",
                    "0x" + "2" * 64,
                    42
                )
            polygon_service.generate_hd_address = mock_generate_hd_address
            
            try:
                # Test creating gas deposit - use the actual function signature
                gas_deposit = crud.create_polygon_gas_deposit(
                    db=db,
                    cas_deposit_id=1,
                    matic_required=0.005
                )
                
                assert gas_deposit.cas_deposit_id == 1
                assert gas_deposit.required_matic == 0.005
                assert gas_deposit.polygon_gas_address == "0x1234567890123456789012345678901234567890"
                assert gas_deposit.hd_index == 42
                assert gas_deposit.status == "pending"
                
                print("✅ CRUD operations successful")
                return True
                
            finally:
                polygon_service.generate_hd_address = original_generate
                
        finally:
            try:
                db.close()
                if os.path.exists(db_path):
                    os.unlink(db_path)
            except:
                pass  # Ignore cleanup errors
            
    except Exception as e:
        print(f"❌ CRUD operations test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("========================================")
    print("Running BYO-gas Functionality Tests")
    print("========================================")
    
    tests = [
        ("Schema Import", test_schemas),
        ("HD Wallet Generation", test_hd_wallet),
        ("Database Migration", test_database_migration),
        ("CRUD Operations", test_crud_operations),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\n--- Testing {name} ---")
        if test_func():
            passed += 1
        else:
            print(f"❌ {name} test failed")
    
    print("\n========================================")
    print(f"Test Results: {passed}/{total} passed")
    print("========================================")
    
    if passed == total:
        print("🎉 All BYO-gas tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 