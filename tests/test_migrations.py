"""
Tests for database migrations
"""
import pytest
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from database.migrations import (
    column_exists,
    add_column_if_not_exists,
    run_confirmation_tracking_migration,
    run_all_migrations
)

class TestMigrations:
    """Test database migration functionality"""
    
    def test_column_exists_function(self):
        """Test the column_exists function"""
        db = SessionLocal()
        try:
            # Test with known existing column
            assert column_exists(db, "cas_deposits", "id") == True
            
            # Test with non-existing column
            assert column_exists(db, "cas_deposits", "nonexistent_column") == False
            
            # Test with non-existing table
            assert column_exists(db, "nonexistent_table", "id") == False
        finally:
            db.close()
    
    def test_add_column_if_not_exists(self):
        """Test adding columns conditionally"""
        db = SessionLocal()
        try:
            # Test column name that should not exist
            test_column = "test_migration_column"
            
            # Ensure column doesn't exist first
            if column_exists(db, "cas_deposits", test_column):
                db.execute(text(f"ALTER TABLE cas_deposits DROP COLUMN {test_column}"))
                db.commit()
            
            # Add the column
            add_column_if_not_exists(db, "cas_deposits", test_column, "INTEGER DEFAULT 0")
            
            # Verify it was added
            assert column_exists(db, "cas_deposits", test_column) == True
            
            # Try adding it again - should not fail
            add_column_if_not_exists(db, "cas_deposits", test_column, "INTEGER DEFAULT 0")
            
            # Clean up
            db.execute(text(f"ALTER TABLE cas_deposits DROP COLUMN {test_column}"))
            db.commit()
            
        finally:
            db.close()
    
    def test_confirmation_tracking_migration_idempotent(self):
        """Test that the confirmation tracking migration is idempotent"""
        db = SessionLocal()
        try:
            # Run migration multiple times - should not fail
            run_confirmation_tracking_migration(db)
            run_confirmation_tracking_migration(db)
            run_confirmation_tracking_migration(db)
            
            # Verify all columns exist
            assert column_exists(db, "cas_deposits", "current_confirmations") == True
            assert column_exists(db, "cas_deposits", "required_confirmations") == True
            assert column_exists(db, "cas_deposits", "deposit_tx_hash") == True
            assert column_exists(db, "polygon_transactions", "current_confirmations") == True
            assert column_exists(db, "polygon_transactions", "required_confirmations") == True
            
        finally:
            db.close()
    
    def test_all_migrations_can_run(self):
        """Test that all migrations can run without errors"""
        db = SessionLocal()
        try:
            # This should not raise any exceptions
            run_all_migrations(db)
            
            # Verify key columns exist after migration
            assert column_exists(db, "cas_deposits", "current_confirmations") == True
            assert column_exists(db, "polygon_transactions", "current_confirmations") == True
            
        finally:
            db.close()
    
    def test_migration_sets_default_values(self):
        """Test that migration sets proper default values for existing records"""
        db = SessionLocal()
        try:
            # Create a test record without confirmation fields (if they exist, drop and recreate)
            # This simulates an existing database before migration
            
            # Run migration to ensure columns exist with defaults
            run_confirmation_tracking_migration(db)
            
            # Insert a test record
            db.execute(text("""
                INSERT INTO cas_deposits (polygon_address, cascoin_deposit_address, status)
                VALUES ('0x1234567890123456789012345678901234567890', 'test_address_123', 'pending')
            """))
            db.commit()
            
            # Check that default values are set
            result = db.execute(text("""
                SELECT current_confirmations, required_confirmations 
                FROM cas_deposits 
                WHERE cascoin_deposit_address = 'test_address_123'
            """)).fetchone()
            
            assert result is not None
            assert result[0] == 0  # current_confirmations default
            assert result[1] == 12  # required_confirmations default
            
            # Clean up
            db.execute(text("DELETE FROM cas_deposits WHERE cascoin_deposit_address = 'test_address_123'"))
            db.commit()
            
        finally:
            db.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 