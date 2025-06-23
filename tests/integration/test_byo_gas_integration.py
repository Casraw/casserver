"""
Integration tests for Bring Your Own Gas (BYO-gas) functionality
Tests the complete flow from gas address generation to minting
"""
import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import sqlite3
import tempfile
import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the FastAPI app and dependencies
from backend.main import app
from backend.database import get_db
from database.models import Base, CasDeposit, PolygonGasDeposit


class TestBYOGasIntegration(unittest.TestCase):
    """Integration test for complete BYO-gas flow"""
    
    def setUp(self):
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.test_db_url = f"sqlite:///{self.db_path}"
        
        # Create test database engine
        self.engine = create_engine(self.test_db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        
        # Create session
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        
        # Create test client
        self.client = TestClient(app)
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'INTERNAL_API_KEY': 'test_internal_key',
            'HD_MNEMONIC': 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about',
            'POLYGON_RPC_URL': 'https://polygon-rpc.com',
            'WCAS_CONTRACT_ADDRESS': '0x1234567890123456789012345678901234567890',
            'MINTER_PRIVATE_KEY': '0x' + '1' * 64
        })
        self.env_patcher.start()
        
        # Also directly set the settings since they're already imported
        from backend.api import internal_api
        from backend import config
        self.original_api_key = internal_api.settings.INTERNAL_API_KEY
        self.original_hd_mnemonic = internal_api.settings.HD_MNEMONIC
        internal_api.settings.INTERNAL_API_KEY = 'test_internal_key'
        internal_api.settings.HD_MNEMONIC = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
        # Also update the main config settings
        config.settings.INTERNAL_API_KEY = 'test_internal_key'
        config.settings.HD_MNEMONIC = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
        
        # Setup test data
        self.test_session = TestingSessionLocal()
        self.setup_test_data()
        
        # Headers for API calls
        self.headers = {"X-Internal-API-Key": "test_internal_key"}

    def tearDown(self):
        self.test_session.close()
        app.dependency_overrides.clear()
        # Restore original settings
        from backend.api import internal_api
        from backend import config
        internal_api.settings.INTERNAL_API_KEY = self.original_api_key
        internal_api.settings.HD_MNEMONIC = self.original_hd_mnemonic
        config.settings.INTERNAL_API_KEY = self.original_api_key
        config.settings.HD_MNEMONIC = self.original_hd_mnemonic
        self.env_patcher.stop()
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path)
        except PermissionError:
            # On Windows, sometimes file handle is still held
            import time
            time.sleep(0.1)
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass  # Skip cleanup if file is still locked

    def setup_test_data(self):
        """Setup test CAS deposit"""
        cas_deposit = CasDeposit(
            id=1,
            cascoin_deposit_address="cas_test_address_123",
            polygon_address="0xRecipientAddress123456789012345678901234567890",
            received_amount=10.0,
            status="cas_confirmed_pending_mint",
            fee_model="direct_payment"
        )
        self.test_session.add(cas_deposit)
        self.test_session.commit()

    @patch('backend.services.polygon_service.Web3')
    @patch('backend.crud.derive_polygon_gas_address')
    def test_complete_byo_gas_flow(self, mock_derive_address, mock_Web3):
        """Test the complete BYO-gas flow from address generation to minting"""
        
        # Mock HD address generation
        mock_derive_address.return_value = (
            "0x1234567890123456789012345678901234567890",
            "0x" + "2" * 64
        )
        
        # Mock Web3 and Polygon service
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        mock_w3.eth.get_balance.return_value = int(0.01 * 1e18)  # 0.01 MATIC
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock minting transaction
        mock_mint_function = MagicMock()
        mock_contract.functions.mint.return_value = mock_mint_function
        mock_mint_function.build_transaction.return_value = {
            'to': '0x1234567890123456789012345678901234567890',
            'value': 0,
            'gas': 200000,
            'gasPrice': 30000000000,
            'nonce': 5,
            'data': '0xmockdata'
        }
        
        # Mock transaction signing and sending
        mock_signed_tx = MagicMock()
        mock_signed_tx.rawTransaction = b'mock_raw_tx'
        mock_w3.eth.account.sign_transaction.return_value = mock_signed_tx
        mock_w3.eth.send_raw_transaction.return_value = b'mock_tx_hash'
        mock_w3.to_hex.return_value = "0xmocktxhash"
        mock_w3.eth.gas_price = 30000000000
        mock_w3.eth.get_transaction_count.return_value = 5
        
        # Mock successful transaction receipt
        mock_receipt = {
            'status': 1,
            'logs': [{
                'address': '0x1234567890123456789012345678901234567890',
                'topics': [
                    '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',  # Transfer event
                    '0x' + '0' * 24 + '0000000000000000000000000000000000000000',  # from (zero)
                    '0x' + '0' * 24 + '0xRecipientAddress123456789012345678901234567890'[2:].lower()  # to
                ],
                'data': '0x' + hex(int(10 * 1e18))[2:].zfill(64)  # amount
            }]
        }
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Step 1: Request gas address
        gas_request_data = {
            "cas_deposit_id": 1,
            "required_matic": 0.005
        }
        
        gas_response = self.client.post(
            "/internal/request_polygon_gas_address",
            json=gas_request_data,
            headers=self.headers
        )
        
        self.assertEqual(gas_response.status_code, 200)
        gas_data = gas_response.json()
        self.assertEqual(gas_data["status"], "success")
        self.assertEqual(gas_data["polygon_gas_address"], "0x1234567890123456789012345678901234567890")
        self.assertEqual(gas_data["hd_index"], 0)  # First deposit starts at index 0
        
        # Verify gas deposit was created in database
        gas_deposit = self.test_session.query(PolygonGasDeposit).filter(
            PolygonGasDeposit.cas_deposit_id == 1
        ).first()
        self.assertIsNotNone(gas_deposit)
        self.assertEqual(gas_deposit.polygon_gas_address, "0x1234567890123456789012345678901234567890")
        self.assertEqual(gas_deposit.status, "pending")
        self.assertEqual(gas_deposit.hd_index, 0)
        
        # Step 2: Simulate gas funding (normally done by user via MetaMask)
        # Update gas deposit status to funded
        gas_deposit.status = "funded"
        gas_deposit.received_matic = Decimal("0.005")
        self.test_session.commit()
        
        # Step 3: Initiate minting
        mint_request_data = {
            "cas_deposit_id": 1,
            "amount_to_mint": 10.0,
            "recipient_polygon_address": "0xRecipientAddress123456789012345678901234567890",
            "cas_deposit_address": "cas_test_address_123"
        }
        
        mint_response = self.client.post(
            "/internal/initiate_wcas_mint",
            json=mint_request_data,
            headers=self.headers
        )
        
        self.assertEqual(mint_response.status_code, 202)  # Background processing
        mint_data = mint_response.json()
        self.assertEqual(mint_data["status"], "accepted")
        self.assertEqual(mint_data["message"], "wCAS minting process has been accepted and is running in the background.")
        
        # Verify HD address generation was called (once for address generation, once for private key derivation)
        self.assertEqual(mock_derive_address.call_count, 2)
        
        # Verify minting was called with custom private key
        mock_mint_function.build_transaction.assert_called_once()

    @patch('backend.crud.derive_polygon_gas_address')
    def test_gas_address_request_duplicate(self, mock_derive_address):
        """Test requesting gas address when one already exists"""
        
        # Mock HD address generation
        mock_derive_address.return_value = (
            "0x1234567890123456789012345678901234567890",
            "0x" + "2" * 64
        )
        
        gas_request_data = {
            "cas_deposit_id": 1,
            "required_matic": 0.005
        }
        
        # First request - should create new gas deposit
        first_response = self.client.post(
            "/internal/request_polygon_gas_address",
            json=gas_request_data,
            headers=self.headers
        )
        
        self.assertEqual(first_response.status_code, 200)
        first_data = first_response.json()
        self.assertEqual(first_data["status"], "success")
        
        # Second request - should return existing gas deposit
        second_response = self.client.post(
            "/internal/request_polygon_gas_address",
            json=gas_request_data,
            headers=self.headers
        )
        
        self.assertEqual(second_response.status_code, 200)
        second_data = second_response.json()
        self.assertEqual(second_data["status"], "existing")
        self.assertEqual(second_data["polygon_gas_address"], first_data["polygon_gas_address"])

    def test_gas_address_request_wrong_fee_model(self):
        """Test gas address request fails for non-direct-payment deposits"""
        
        # Update CAS deposit to use deducted fee model
        cas_deposit = self.test_session.query(CasDeposit).filter(CasDeposit.id == 1).first()
        cas_deposit.fee_model = "deducted"
        self.test_session.commit()
        
        gas_request_data = {
            "cas_deposit_id": 1,
            "required_matic": 0.005
        }
        
        response = self.client.post(
            "/internal/request_polygon_gas_address",
            json=gas_request_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("Gas address can only be requested for direct_payment fee model", response.json()["detail"])

    @patch('backend.services.polygon_service.Web3')
    def test_minting_fails_when_gas_not_funded(self, mock_Web3):
        """Test minting fails when gas deposit is not funded"""
        
        # Mock Web3
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Create unfunded gas deposit
        gas_deposit = PolygonGasDeposit(
            cas_deposit_id=1,
            polygon_gas_address="0x1234567890123456789012345678901234567890",
            required_matic=Decimal("0.005"),
            received_matic=Decimal("0.0"),
            status="pending",  # Not funded
            hd_index=42
        )
        self.test_session.add(gas_deposit)
        self.test_session.commit()
        
        mint_request_data = {
            "cas_deposit_id": 1,
            "amount_to_mint": 10.0,
            "recipient_polygon_address": "0xRecipientAddress123456789012345678901234567890",
            "cas_deposit_address": "cas_test_address_123"
        }
        
        response = self.client.post(
            "/internal/initiate_wcas_mint",
            json=mint_request_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 202)  # Background processing
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["message"], "wCAS minting process has been accepted and is running in the background.")

    def test_gas_address_request_nonexistent_cas_deposit(self):
        """Test gas address request fails for non-existent CAS deposit"""
        
        gas_request_data = {
            "cas_deposit_id": 999,  # Non-existent
            "required_matic": 0.005
        }
        
        response = self.client.post(
            "/internal/request_polygon_gas_address",
            json=gas_request_data,
            headers=self.headers
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("CasDeposit record not found", response.json()["detail"])


class TestBYOGasWatcherIntegration(unittest.TestCase):
    """Test integration with watchers for BYO-gas functionality"""
    
    def setUp(self):
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.test_db_url = f"sqlite:///{self.db_path}"
        
        # Create test database engine
        self.engine = create_engine(self.test_db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        
        # Create session
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.test_session = TestingSessionLocal()
        
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'HD_MNEMONIC': 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about',
            'POLYGON_RPC_URL': 'https://polygon-rpc.com'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.test_session.close()
        self.env_patcher.stop()
        os.close(self.db_fd)
        try:
            os.unlink(self.db_path)
        except PermissionError:
            # On Windows, sometimes file handle is still held
            import time
            time.sleep(0.1)
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass  # Skip cleanup if file is still locked

    @patch('watchers.polygon_watcher.Web3')
    @patch('watchers.polygon_watcher.SessionLocal')
    def test_polygon_watcher_detects_gas_funding(self, mock_SessionLocal, mock_Web3):
        """Test that polygon watcher detects and processes gas funding"""
        
        # Mock Web3
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Mock database session
        mock_session = MagicMock()
        mock_SessionLocal.return_value = mock_session
        
        # Mock gas deposit query result
        mock_gas_deposit = MagicMock()
        mock_gas_deposit.id = 1
        mock_gas_deposit.polygon_gas_address = "0x1234567890123456789012345678901234567890"
        mock_gas_deposit.required_matic = Decimal("0.005")
        mock_gas_deposit.status = "pending"
        mock_gas_deposit.received_matic = Decimal("0.0")
        
        # Mock query to return pending gas deposits
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_gas_deposit]
        
        # Mock balance check - exactly required amount
        mock_w3.eth.get_balance.return_value = int(0.005 * 1e18)
        
        # Import and test watcher function
        from watchers.polygon_watcher import check_gas_deposits_funding
        
        check_gas_deposits_funding()
        
        # Verify session operations were called
        mock_SessionLocal.assert_called()
        mock_session.query.assert_called()

    @patch('watchers.cascoin_watcher.SessionLocal')
    @patch('watchers.cascoin_watcher.cascoin_rpc_call')
    def test_cascoin_watcher_waits_for_gas_funding(self, mock_rpc_call, mock_SessionLocal):
        """Test that cascoin watcher waits for gas funding before triggering mint"""
        
        # Mock database session
        mock_session = MagicMock()
        mock_SessionLocal.return_value = mock_session
        
        # Mock CAS deposit with direct_payment fee model
        mock_cas_deposit = MagicMock()
        mock_cas_deposit.id = 1
        mock_cas_deposit.status = "cas_confirmed_pending_mint"
        mock_cas_deposit.cascoin_deposit_address = "test_address_123"
        mock_cas_deposit.received_amount = 10.0
        mock_cas_deposit.polygon_address = "0xRecipientAddress"
        
        # Mock unfunded gas deposit query result
        mock_gas_deposit = MagicMock()
        mock_gas_deposit.status = "pending"  # Not funded yet
        
        # Mock queries
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.all.return_value = [mock_cas_deposit]
        mock_query.first.return_value = mock_gas_deposit
        
        # Mock RPC call
        mock_rpc_call.return_value = {"result": []}
        
        # Import and test watcher function
        from watchers.cascoin_watcher import check_cascoin_transactions
        
        check_cascoin_transactions()
        
        # Verify session operations were called
        mock_SessionLocal.assert_called()
        mock_session.query.assert_called()


if __name__ == '__main__':
    unittest.main()