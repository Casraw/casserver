"""
Tests for CRUD operations related to Bring Your Own Gas (BYO-gas) functionality
"""
import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend import crud
from backend.schemas import PolygonGasDepositCreate
from database.models import PolygonGasDeposit, CasDeposit


class TestPolygonGasDepositCRUD(unittest.TestCase):
    """Test CRUD operations for PolygonGasDeposit"""
    
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        self.mock_query = MagicMock()
        self.mock_db.query.return_value = self.mock_query
        
        # Sample data
        self.sample_gas_deposit_data = PolygonGasDepositCreate(
            cas_deposit_id=1,
            polygon_gas_address="0x1234567890123456789012345678901234567890",
            required_matic=Decimal("0.005"),
            hd_index=42
        )
        
        self.mock_gas_deposit = PolygonGasDeposit(
            id=1,
            cas_deposit_id=1,
            polygon_gas_address="0x1234567890123456789012345678901234567890",
            required_matic=Decimal("0.005"),
            received_matic=Decimal("0.0"),
            status="pending",
            hd_index=42,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    def test_create_polygon_gas_deposit_success(self):
        """Test successful creation of polygon gas deposit"""
        # Mock the database session and HD wallet functions
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()
        
        # Mock HD wallet generation
        with patch('backend.crud.get_next_hd_index') as mock_hd_index, \
             patch('backend.crud.derive_polygon_gas_address') as mock_derive:
            mock_hd_index.return_value = 42
            mock_derive.return_value = ("0x1234567890123456789012345678901234567890", "0x123...")
            
            # Call the function with individual parameters
            result = crud.create_polygon_gas_deposit(
                self.mock_db, 
                cas_deposit_id=1, 
                matic_required=0.005
            )
        
                    # Verify database operations
            self.mock_db.add.assert_called_once()
            self.mock_db.commit.assert_called_once()
            self.mock_db.refresh.assert_called_once()
            
            # Verify the created object has correct attributes
            added_obj = self.mock_db.add.call_args[0][0]
            self.assertEqual(added_obj.cas_deposit_id, 1)
            self.assertEqual(added_obj.polygon_gas_address, "0x1234567890123456789012345678901234567890")
            self.assertEqual(added_obj.required_matic, 0.005)
            self.assertEqual(added_obj.hd_index, 42)
            # Status should be set by default in the model (but not in our mock)

    def test_create_polygon_gas_deposit_integrity_error(self):
        """Test creation fails with integrity error (duplicate address)"""
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock(side_effect=IntegrityError("", "", ""))
        self.mock_db.rollback = MagicMock()
        
        # Mock HD wallet generation
        with patch('backend.crud.get_next_hd_index') as mock_hd_index, \
             patch('backend.crud.derive_polygon_gas_address') as mock_derive:
            mock_hd_index.return_value = 42
            mock_derive.return_value = ("0x1234567890123456789012345678901234567890", "0x123...")
            
            # The function should return None on error, not raise
            result = crud.create_polygon_gas_deposit(
                self.mock_db, 
                cas_deposit_id=1, 
                matic_required=0.005
            )
            
            self.assertIsNone(result)
            self.mock_db.rollback.assert_called_once()

    def test_get_polygon_gas_deposit_by_id_found(self):
        """Test getting gas deposit by ID when it exists"""
        self.mock_query.filter.return_value.first.return_value = self.mock_gas_deposit
        
        result = crud.get_polygon_gas_deposit_by_id(self.mock_db, 1)
        
        self.assertEqual(result, self.mock_gas_deposit)
        self.mock_db.query.assert_called_once_with(PolygonGasDeposit)
        self.mock_query.filter.assert_called_once()

    def test_get_polygon_gas_deposit_by_id_not_found(self):
        """Test getting gas deposit by ID when it doesn't exist"""
        self.mock_query.filter.return_value.first.return_value = None
        
        result = crud.get_polygon_gas_deposit_by_id(self.mock_db, 999)
        
        self.assertIsNone(result)

    def test_get_polygon_gas_deposit_by_cas_id_found(self):
        """Test getting gas deposit by CAS deposit ID when it exists"""
        self.mock_query.filter.return_value.first.return_value = self.mock_gas_deposit
        
        result = crud.get_polygon_gas_deposit_by_cas_id(self.mock_db, 1)
        
        self.assertEqual(result, self.mock_gas_deposit)
        self.mock_db.query.assert_called_once_with(PolygonGasDeposit)

    def test_get_polygon_gas_deposit_by_cas_id_not_found(self):
        """Test getting gas deposit by CAS deposit ID when it doesn't exist"""
        self.mock_query.filter.return_value.first.return_value = None
        
        result = crud.get_polygon_gas_deposit_by_cas_id(self.mock_db, 999)
        
        self.assertIsNone(result)

    def test_get_polygon_gas_deposit_by_address_found(self):
        """Test getting gas deposit by address when it exists"""
        self.mock_query.filter.return_value.first.return_value = self.mock_gas_deposit
        
        result = crud.get_polygon_gas_deposit_by_address(
            self.mock_db, 
            "0x1234567890123456789012345678901234567890"
        )
        
        self.assertEqual(result, self.mock_gas_deposit)

    def test_get_polygon_gas_deposit_by_address_not_found(self):
        """Test getting gas deposit by address when it doesn't exist"""
        self.mock_query.filter.return_value.first.return_value = None
        
        result = crud.get_polygon_gas_deposit_by_address(
            self.mock_db, 
            "0xNonExistentAddress"
        )
        
        self.assertIsNone(result)

    def test_update_polygon_gas_deposit_status_success(self):
        """Test successful status update"""
        self.mock_query.filter.return_value.first.return_value = self.mock_gas_deposit
        self.mock_db.commit = MagicMock()
        
        result = crud.update_polygon_gas_deposit_status(
            self.mock_db, 
            gas_deposit_id=1, 
            new_status="funded"
        )
        
        self.assertEqual(result.status, "funded")
        self.mock_db.commit.assert_called_once()

    def test_update_polygon_gas_deposit_status_not_found(self):
        """Test status update when gas deposit doesn't exist"""
        self.mock_query.filter.return_value.first.return_value = None
        
        result = crud.update_polygon_gas_deposit_status(
            self.mock_db, 
            gas_deposit_id=999, 
            new_status="funded"
        )
        
        self.assertIsNone(result)

    def test_update_polygon_gas_deposit_received_matic_success(self):
        """Test successful received MATIC update"""
        self.mock_query.filter.return_value.first.return_value = self.mock_gas_deposit
        self.mock_db.commit = MagicMock()
        
        result = crud.update_polygon_gas_deposit_received_matic(
            self.mock_db, 
            gas_deposit_id=1, 
            received_matic=Decimal("0.005")
        )
        
        self.assertEqual(result.received_matic, Decimal("0.005"))
        self.mock_db.commit.assert_called_once()

    def test_get_pending_polygon_gas_deposits(self):
        """Test getting all pending gas deposits"""
        mock_deposits = [self.mock_gas_deposit]
        self.mock_query.filter.return_value.all.return_value = mock_deposits
        
        result = crud.get_pending_polygon_gas_deposits(self.mock_db)
        
        self.assertEqual(result, mock_deposits)
        self.mock_db.query.assert_called_once_with(PolygonGasDeposit)

    def test_get_funded_polygon_gas_deposits(self):
        """Test getting all funded gas deposits"""
        mock_deposits = [self.mock_gas_deposit]
        self.mock_query.filter.return_value.all.return_value = mock_deposits
        
        result = crud.get_funded_polygon_gas_deposits(self.mock_db)
        
        self.assertEqual(result, mock_deposits)


class TestHDWalletIntegration(unittest.TestCase):
    """Test HD wallet integration with CRUD operations"""
    
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        
    @patch('backend.crud.get_next_hd_index')
    @patch('backend.crud.derive_polygon_gas_address')
    def test_create_polygon_gas_deposit_with_hd_generation(self, mock_derive, mock_hd_index):
        """Test gas deposit creation with HD address generation"""
        # Mock HD wallet functions
        mock_hd_index.return_value = 42
        mock_derive.return_value = (
            "0x1234567890123456789012345678901234567890",
            "0x1234567890123456789012345678901234567890123456789012345678901234"
        )
        
        self.mock_db.add = MagicMock()
        self.mock_db.commit = MagicMock()
        self.mock_db.refresh = MagicMock()
        
        gas_deposit_data = PolygonGasDepositCreate(
            cas_deposit_id=1,
            required_matic=Decimal("0.005")
        )
        
        result = crud.create_polygon_gas_deposit(
            self.mock_db, 
            cas_deposit_id=gas_deposit_data.cas_deposit_id, 
            matic_required=float(gas_deposit_data.required_matic)
        )
        
        # Verify HD functions were called
        mock_hd_index.assert_called_once()
        mock_derive.assert_called_once_with(42)
        
        # Verify the created object has HD-generated address
        added_obj = self.mock_db.add.call_args[0][0]
        self.assertEqual(added_obj.polygon_gas_address, "0x1234567890123456789012345678901234567890")
        self.assertEqual(added_obj.hd_index, 42)

    @patch('backend.crud.derive_polygon_gas_address')
    def test_create_polygon_gas_deposit_hd_generation_failure(self, mock_derive):
        """Test gas deposit creation when HD generation fails"""
        mock_derive.side_effect = Exception("HD generation failed")
        
        gas_deposit_data = PolygonGasDepositCreate(
            cas_deposit_id=1,
            required_matic=Decimal("0.005")
        )
        
        result = crud.create_polygon_gas_deposit(
            self.mock_db, 
            cas_deposit_id=gas_deposit_data.cas_deposit_id, 
            matic_required=float(gas_deposit_data.required_matic)
        )
        
        # Should return None on error
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main() 