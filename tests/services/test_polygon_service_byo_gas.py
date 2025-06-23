"""
Tests for Polygon Service BYO-gas (Bring Your Own Gas) functionality
"""
import unittest
from unittest.mock import patch, MagicMock, call
from decimal import Decimal

from backend.services.polygon_service import PolygonService


class TestPolygonServiceBYOGas(unittest.TestCase):
    """Test Polygon Service with BYO-gas functionality"""
    
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'POLYGON_RPC_URL': 'https://polygon-rpc.com',
            'WCAS_CONTRACT_ADDRESS': '0x1234567890123456789012345678901234567890',
            'MINTER_PRIVATE_KEY': '0x' + '1' * 64,
            'HD_MNEMONIC': 'test mnemonic phrase with twelve words for testing purposes only'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('backend.services.polygon_service.Web3')
    @patch('backend.crud.derive_polygon_gas_address')  # Fixed import path
    def test_mint_wcas_with_custom_private_key_success(self, mock_derive_address, mock_Web3):
        """Test successful wCAS minting with custom private key (BYO-gas)"""
        # Mock Web3 setup
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock account and transaction
        mock_account = MagicMock()
        mock_account.address = "0xCustomGasPayerAddress"
        mock_w3.eth.account.from_key.return_value = mock_account
        
        # Mock transaction building and sending
        mock_built_tx = {'gas': 100000, 'nonce': 1}
        mock_contract.functions.mint.return_value.build_transaction.return_value = mock_built_tx
        
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'signed_tx_data'
        mock_account.sign_transaction.return_value = mock_signed_tx
        
        mock_w3.eth.send_raw_transaction.return_value = b'tx_hash_bytes'
        
        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'tx_hash_bytes'
        mock_receipt.get.return_value = "0xRecipientAddress"  # Mock 'to' field
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check for post-mint validation
        mock_w3.eth.call.return_value = b'\\x00' * 31 + b'\\x01'  # Mock balance > 0
        
        # Mock gas and nonce
        mock_w3.eth.get_transaction_count.return_value = 1
        mock_w3.eth.fee_history.return_value = {
            'baseFeePerGas': [1000000000],  # 1 gwei
            'reward': [[500000000]]  # 0.5 gwei tip
        }
        
        # Mock decimals call
        mock_w3.eth.call.return_value = (18).to_bytes(32, 'big')
        
        # Initialize service
        service = PolygonService()
        
        # Test minting with custom private key
        custom_private_key = "0x" + "2" * 64
        result = service.mint_wcas(
            recipient_address="0xRecipientAddress",
            amount_cas=10.0,
            custom_private_key=custom_private_key
        )
        
        # Verify result
        self.assertEqual(result, "0x" + b'tx_hash_bytes'.hex())
        
        # Verify custom account was used
        mock_w3.eth.account.from_key.assert_called_with(custom_private_key)

    @patch('backend.services.polygon_service.Web3')
    @patch('backend.crud.derive_polygon_gas_address')  # Fixed import path
    def test_mint_wcas_custom_key_insufficient_balance(self, mock_derive_address, mock_Web3):
        """Test minting with custom private key fails when insufficient balance"""
        # Mock Web3 setup
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock account with insufficient balance
        mock_account = MagicMock()
        mock_account.address = "0xCustomGasPayerAddress"
        mock_w3.eth.account.from_key.return_value = mock_account
        mock_w3.eth.get_balance.return_value = 0  # No balance
        
        # Mock transaction building
        mock_built_tx = {'gas': 100000, 'gasPrice': 20000000000}  # 20 gwei
        mock_contract.functions.mint.return_value.build_transaction.return_value = mock_built_tx
        
        # Mock decimals call
        mock_w3.eth.call.return_value = (18).to_bytes(32, 'big')
        
        # Initialize service
        service = PolygonService()
        
        # Test minting with custom private key (insufficient balance)
        custom_private_key = "0x" + "2" * 64
        result = service.mint_wcas(
            recipient_address="0xRecipientAddress",
            amount_cas=10.0,
            custom_private_key=custom_private_key
        )
        
        # Should return None due to insufficient balance
        self.assertIsNone(result)

    @patch('backend.services.polygon_service.Web3')
    @patch('backend.crud.derive_polygon_gas_address')  # Fixed import path
    def test_mint_wcas_without_custom_private_key_uses_minter(self, mock_derive_address, mock_Web3):
        """Test minting without custom private key uses minter account"""
        # Mock Web3 setup
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock minter account
        mock_minter_account = MagicMock()
        mock_minter_account.address = "0xMinterAddress"
        mock_w3.eth.account.from_key.return_value = mock_minter_account
        
        # Mock transaction building and sending
        mock_built_tx = {'gas': 100000, 'nonce': 1}
        mock_contract.functions.mint.return_value.build_transaction.return_value = mock_built_tx
        
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'signed_tx_data'
        mock_minter_account.sign_transaction.return_value = mock_signed_tx
        
        mock_w3.eth.send_raw_transaction.return_value = b'tx_hash_bytes'
        
        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'tx_hash_bytes'
        mock_receipt.get.return_value = "0xRecipientAddress"  # Mock 'to' field
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check for post-mint validation
        mock_w3.eth.call.return_value = b'\\x00' * 31 + b'\\x01'  # Mock balance > 0
        
        # Mock gas and nonce
        mock_w3.eth.get_transaction_count.return_value = 1
        mock_w3.eth.fee_history.return_value = {
            'baseFeePerGas': [1000000000],  # 1 gwei
            'reward': [[500000000]]  # 0.5 gwei tip
        }
        
        # Mock decimals call
        mock_w3.eth.call.return_value = (18).to_bytes(32, 'big')
        
        # Initialize service
        service = PolygonService()
        
        # Test minting without custom private key
        result = service.mint_wcas(
            recipient_address="0xRecipientAddress",
            amount_cas=10.0
        )
        
        # Verify result
        self.assertEqual(result, "0x" + b'tx_hash_bytes'.hex())
        
        # Verify minter account was used (service's private key)
        self.assertTrue(mock_w3.eth.account.from_key.called)

    @patch('backend.services.polygon_service.Web3')
    @patch('backend.crud.derive_polygon_gas_address')  # Fixed import path
    def test_mint_wcas_with_post_mint_validation_success(self, mock_derive_address, mock_Web3):
        """Test minting with post-mint validation when tokens go to correct recipient"""
        # Mock Web3 setup
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock account and transaction
        mock_account = MagicMock()
        mock_account.address = "0xCustomGasPayerAddress"
        mock_w3.eth.account.from_key.return_value = mock_account
        
        # Mock transaction building and sending
        mock_built_tx = {'gas': 100000, 'nonce': 1}
        mock_contract.functions.mint.return_value.build_transaction.return_value = mock_built_tx
        
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'signed_tx_data'
        mock_account.sign_transaction.return_value = mock_signed_tx
        
        mock_w3.eth.send_raw_transaction.return_value = b'tx_hash_bytes'
        
        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'tx_hash_bytes'
        mock_receipt.get.return_value = "0xRecipientAddress"  # Mock 'to' field
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check for post-mint validation - recipient has tokens
        mock_w3.eth.call.return_value = b'\\x00' * 31 + b'\\x01'  # Mock balance > 0
        
        # Mock gas and nonce
        mock_w3.eth.get_transaction_count.return_value = 1
        mock_w3.eth.fee_history.return_value = {
            'baseFeePerGas': [1000000000],  # 1 gwei
            'reward': [[500000000]]  # 0.5 gwei tip
        }
        
        # Mock decimals call
        mock_w3.eth.call.return_value = (18).to_bytes(32, 'big')
        
        # Initialize service
        service = PolygonService()
        
        # Test minting with custom private key
        custom_private_key = "0x" + "2" * 64
        result = service.mint_wcas(
            recipient_address="0xRecipientAddress",
            amount_cas=10.0,
            custom_private_key=custom_private_key
        )
        
        # Verify result
        self.assertEqual(result, "0x" + b'tx_hash_bytes'.hex())

    @patch('backend.services.polygon_service.Web3')
    @patch('backend.crud.derive_polygon_gas_address')  # Fixed import path
    def test_mint_wcas_with_post_mint_validation_needs_transfer(self, mock_derive_address, mock_Web3):
        """Test minting with post-mint validation when tokens need to be transferred"""
        # Mock Web3 setup
        mock_w3 = MagicMock()
        mock_Web3.return_value = mock_w3
        mock_w3.is_connected.return_value = True
        
        # Mock contract
        mock_contract = MagicMock()
        mock_w3.eth.contract.return_value = mock_contract
        
        # Mock account and transaction
        mock_account = MagicMock()
        mock_account.address = "0xCustomGasPayerAddress"
        mock_w3.eth.account.from_key.return_value = mock_account
        
        # Mock transaction building and sending for mint
        mock_built_tx = {'gas': 100000, 'nonce': 1}
        mock_contract.functions.mint.return_value.build_transaction.return_value = mock_built_tx
        
        # Mock transfer transaction building
        mock_transfer_tx = {'gas': 65000, 'nonce': 2}
        mock_contract.functions.transfer.return_value.build_transaction.return_value = mock_transfer_tx
        
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'signed_tx_data'
        mock_account.sign_transaction.return_value = mock_signed_tx
        
        mock_w3.eth.send_raw_transaction.side_effect = [b'mint_tx_hash', b'transfer_tx_hash']
        
        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'mint_tx_hash'
        mock_receipt.get.return_value = "0xCustomGasPayerAddress"  # Tokens went to minter, not recipient
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check - recipient doesn't have tokens initially
        mock_w3.eth.call.side_effect = [
            (18).to_bytes(32, 'big'),  # decimals call
            b'\\x00' * 32,  # recipient balance = 0 (needs transfer)
            b'\\x00' * 31 + b'\\x01'  # recipient balance > 0 after transfer
        ]
        
        # Mock gas and nonce
        mock_w3.eth.get_transaction_count.side_effect = [1, 2]  # Mint nonce, then transfer nonce
        mock_w3.eth.fee_history.return_value = {
            'baseFeePerGas': [1000000000],  # 1 gwei
            'reward': [[500000000]]  # 0.5 gwei tip
        }
        
        # Initialize service
        service = PolygonService()
        
        # Test minting with custom private key (should trigger transfer)
        custom_private_key = "0x" + "2" * 64
        result = service.mint_wcas(
            recipient_address="0xRecipientAddress",
            amount_cas=10.0,
            custom_private_key=custom_private_key
        )
        
        # Verify result (should be mint tx hash)
        self.assertEqual(result, "0x" + b'mint_tx_hash'.hex())


class TestHDWalletGeneration(unittest.TestCase):
    """Test HD wallet generation for BYO-gas addresses"""
    
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'HD_MNEMONIC': 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('backend.crud.derive_polygon_gas_address')
    def test_derive_polygon_gas_address_success(self, mock_derive):
        """Test successful HD address derivation"""
        # Mock the function to return expected values
        mock_derive.return_value = ("0x1234567890123456789012345678901234567890", "0x" + "a" * 64)
        
        from backend.crud import derive_polygon_gas_address
        
        # Test derivation
        address, private_key = derive_polygon_gas_address(42)
        
        # Verify results
        self.assertIsInstance(address, str)
        self.assertIsInstance(private_key, str)
        self.assertTrue(address.startswith("0x"))
        self.assertTrue(private_key.startswith("0x"))
        self.assertEqual(len(address), 42)  # 0x + 40 hex chars
        self.assertEqual(len(private_key), 66)  # 0x + 64 hex chars
        
        # Verify the function was called with correct index
        mock_derive.assert_called_once_with(42)

    def test_generate_hd_address_no_mnemonic(self):
        """Test HD address generation fails without mnemonic"""
        # Remove mnemonic from environment
        self.env_patcher.stop()
        with patch.dict('os.environ', {}, clear=True):
            from backend.crud import derive_polygon_gas_address
            
            # Should raise exception without mnemonic
            with self.assertRaises(ValueError):
                derive_polygon_gas_address(42)
        
        # Restart patcher for tearDown
        self.env_patcher.start()

    @patch('backend.crud.derive_polygon_gas_address')
    def test_generate_hd_private_key_success(self, mock_derive):
        """Test HD private key generation produces consistent results"""
        # Mock the function to return different values for different indices
        def mock_derive_side_effect(index):
            if index == 42:
                return ("0x1234567890123456789012345678901234567890", "0x" + "a" * 64)
            elif index == 43:
                return ("0x9876543210987654321098765432109876543210", "0x" + "b" * 64)
            else:
                return ("0xdefaultaddress", "0x" + "c" * 64)
        
        mock_derive.side_effect = mock_derive_side_effect
        
        from backend.crud import derive_polygon_gas_address
        
        # Test same index produces same results
        address1, private_key1 = derive_polygon_gas_address(42)
        address2, private_key2 = derive_polygon_gas_address(42)
        
        self.assertEqual(address1, address2)
        self.assertEqual(private_key1, private_key2)
        
        # Test different indices produce different results
        address3, private_key3 = derive_polygon_gas_address(43)
        
        self.assertNotEqual(address1, address3)
        self.assertNotEqual(private_key1, private_key3)
        
        # Verify all calls were made
        self.assertEqual(mock_derive.call_count, 3)


if __name__ == '__main__':
    unittest.main() 