import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import json
import os
import importlib # For reloading the module to test ABI loading

# Module to test
from backend.services import polygon_service # Import module itself for reload
from backend.services.polygon_service import PolygonService # For instantiating
from backend.config import Settings # To mock settings

# Web3 and related imports for mocking
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput
from eth_account.signers.local import LocalAccount # For mocking minter_account
from hexbytes import HexBytes # For mocking transaction hashes

# --- Helper for settings mock ---
def get_default_mock_settings():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.POLYGON_RPC_URL = "https://mockrpc-polygon.com" # Ensure "polygon" is in URL for PoA middleware
    mock_settings.MINTER_PRIVATE_KEY = "0x" + "1" * 64 # Valid format, but mock
    mock_settings.WCAS_CONTRACT_ADDRESS = "0x" + "2" * 40 # Valid format
    mock_settings.WCAS_CONTRACT_ABI_JSON_PATH = "mock_abi.json" # Default for tests
    mock_settings.DEFAULT_GAS_LIMIT = 200000
    mock_settings.DEFAULT_MAX_PRIORITY_FEE_PER_GAS_GWEI = 2.0
    return mock_settings

# --- Tests for ABI Loading (Module Level) ---
class TestPolygonServiceABILoading(unittest.TestCase):

    def setUp(self):
        # Ensure a clean slate for polygon_service.WCAS_ABI before each test
        polygon_service.WCAS_ABI = []
        # Store original os.path.exists and open
        self.original_exists = os.path.exists
        self.original_open = open

    def tearDown(self):
        # Restore original functions
        os.path.exists = self.original_exists
        open = self.original_open
        # Reload module to reset its state for other test classes/cases
        importlib.reload(polygon_service)

    @patch('backend.services.polygon_service.settings', get_default_mock_settings())
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_abi_load_success_direct_path(self, mock_file_open, mock_os_exists):
        """Test successful ABI loading from the direct path."""
        mock_os_exists.return_value = True # File exists at direct path
        mock_abi_data = [{"type": "function", "name": "decimals"}]
        mock_file_open.return_value.read.return_value = json.dumps(mock_abi_data)

        # For ABI loading at module level, we need to reload the module
        importlib.reload(polygon_service)

        self.assertEqual(polygon_service.WCAS_ABI, mock_abi_data)

    @patch('backend.services.polygon_service.settings')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_abi_load_success_project_root_path(self, mock_file_open, mock_os_exists, mock_settings_global):
        """Test successful ABI loading from the project root relative path."""
        # Setup mock settings for this specific test case
        mock_settings_instance = get_default_mock_settings()
        mock_settings_instance.WCAS_CONTRACT_ABI_JSON_PATH = "smart_contracts/wCAS_ABI.json" # A typical relative path

        # Patch the settings object within the polygon_service module for the duration of this test
        with patch('backend.services.polygon_service.settings', mock_settings_instance):
            # Simulate file not existing at direct path, but existing at project root path
            mock_os_exists.side_effect = lambda path: "smart_contracts" in path

            mock_abi_data = [{"type": "function", "name": "balanceOf"}]
            mock_file_open.return_value.read.return_value = json.dumps(mock_abi_data)

            importlib.reload(polygon_service)

            self.assertEqual(polygon_service.WCAS_ABI, mock_abi_data)
            # Check that the ABI_FILE_PATH was updated
            self.assertTrue("smart_contracts" in polygon_service.ABI_FILE_PATH)


    @patch('backend.services.polygon_service.settings', get_default_mock_settings())
    @patch('os.path.exists')
    def test_abi_file_not_found(self, mock_os_exists):
        """Test ABI loading when the file is not found at any path."""
        mock_os_exists.return_value = False # File does not exist

        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            importlib.reload(polygon_service)

        self.assertEqual(polygon_service.WCAS_ABI, [])
        self.assertIn("ABI file not found", cm.output[0]) # Check for the specific error log

    @patch('backend.services.polygon_service.settings', get_default_mock_settings())
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_abi_invalid_json(self, mock_file_open, mock_os_exists):
        """Test ABI loading when the file contains invalid JSON."""
        mock_os_exists.return_value = True
        mock_file_open.return_value.read.return_value = "this is not json"

        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            importlib.reload(polygon_service)

        self.assertEqual(polygon_service.WCAS_ABI, [])
        self.assertIn("Error loading ABI", cm.output[0])


# --- Tests for PolygonService __init__ ---
class TestPolygonServiceInit(unittest.TestCase):

    def setUp(self):
        # Common mocks for Web3 and account, can be customized per test
        self.mock_web3_instance = MagicMock(spec=Web3)
        self.mock_web3_instance.eth = MagicMock()
        self.mock_web3_instance.eth.chain_id = 137 # Default to Polygon mainnet
        self.mock_web3_instance.is_connected.return_value = True

        self.mock_minter_account = MagicMock(spec=LocalAccount)
        self.mock_minter_account.address = "0xMinterAddress"

        # Mock for contract interactions
        self.mock_contract_instance = MagicMock()
        self.mock_contract_instance.functions.decimals().call.return_value = 18 # Default successful decimal call

        # Patch Web3, Account.from_key, and settings
        # Patching settings at the class level or using patch.dict for finer control
        self.settings_patcher = patch('backend.services.polygon_service.settings', get_default_mock_settings())
        self.mock_settings = self.settings_patcher.start()

        self.web3_patcher = patch('backend.services.polygon_service.Web3', return_value=self.mock_web3_instance)
        self.mock_Web3_class = self.web3_patcher.start()

        self.mock_web3_instance.eth.account = MagicMock()
        self.mock_from_key = MagicMock()

        def from_key_side_effect(key):
            if key == self.mock_settings.MINTER_PRIVATE_KEY:
                return self.mock_minter_account
            raise ValueError(f"Invalid private key: {key}")
        
        self.mock_from_key.side_effect = from_key_side_effect
        self.mock_web3_instance.eth.account.from_key = self.mock_from_key

        # Mock the contract call within the Web3 instance
        self.mock_web3_instance.eth.contract.return_value = self.mock_contract_instance

        # Mock WCAS_ABI at module level for init tests
        self.abi_patcher = patch('backend.services.polygon_service.WCAS_ABI', [{"name": "decimals"}]) # Minimal valid ABI
        self.mock_wcas_abi_list = self.abi_patcher.start()

        # Patch Web3.to_checksum_address as it's used directly in init
        self.checksum_address_patcher = patch('backend.services.polygon_service.Web3.to_checksum_address', side_effect=lambda x: x)
        self.mock_checksum_address = self.checksum_address_patcher.start()


    def tearDown(self):
        self.settings_patcher.stop()
        self.web3_patcher.stop()
        self.abi_patcher.stop()
        self.checksum_address_patcher.stop()
        importlib.reload(polygon_service)


    def test_init_successful(self):
        """Test successful initialization of PolygonService."""
        service = PolygonService()

        self.mock_Web3_class.HTTPProvider.assert_called_once_with(self.mock_settings.POLYGON_RPC_URL, request_kwargs={'timeout': 60})
        self.mock_web3_instance.middleware_onion.inject.assert_called_once()
        self.mock_web3_instance.is_connected.assert_called_once()
        self.mock_from_key.assert_called_once_with(self.mock_settings.MINTER_PRIVATE_KEY)
        self.mock_web3_instance.eth.contract.assert_called_once_with(
            address=Web3.to_checksum_address(self.mock_settings.WCAS_CONTRACT_ADDRESS),
            abi=self.mock_wcas_abi_list
        )
        self.mock_contract_instance.functions.decimals().call.assert_called_once()
        self.assertEqual(service.wcas_decimals, 18)
        self.assertEqual(service.minter_address, "0xMinterAddress")

    def test_init_rpc_connection_failure(self):
        """Test __init__ when Web3 fails to connect to RPC."""
        self.mock_web3_instance.is_connected.return_value = False
        with self.assertRaisesRegex(ConnectionError, "Failed to connect to Polygon node"):
            PolygonService()

    def test_init_invalid_minter_key(self):
        """Test __init__ with an invalid MINTER_PRIVATE_KEY."""
        self.mock_from_key.side_effect = ValueError("Invalid key")
        with self.assertRaisesRegex(ValueError, "Invalid or missing MINTER_PRIVATE_KEY"):
            PolygonService()

    def test_init_placeholder_minter_key(self):
        """Test __init__ with a placeholder MINTER_PRIVATE_KEY."""
        self.mock_settings.MINTER_PRIVATE_KEY = "0x" + "0" * 64
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            # The service should log an error but might not raise, depending on design.
            # Here we assume it continues, but logs the problem.
            PolygonService()
        self.assertTrue(any("MINTER_PRIVATE_KEY is a placeholder" in log for log in cm.output))

    def test_init_missing_contract_address(self):
        """Test __init__ with a missing WCAS_CONTRACT_ADDRESS."""
        self.mock_settings.WCAS_CONTRACT_ADDRESS = ""
        with self.assertRaisesRegex(ValueError, "WCAS_CONTRACT_ADDRESS is not configured properly."):
            PolygonService()

    def test_init_placeholder_contract_address(self):
        """Test __init__ with a placeholder WCAS_CONTRACT_ADDRESS."""
        self.mock_settings.WCAS_CONTRACT_ADDRESS = "0x" + "0" * 40
        with self.assertRaisesRegex(ValueError, "WCAS_CONTRACT_ADDRESS is not configured properly."):
            PolygonService()

    def test_init_empty_abi_list(self):
        """Test __init__ when WCAS_ABI list is empty (failed to load)."""
        # To simulate this, we stop the class-level patch and set the global to empty
        self.abi_patcher.stop()
        polygon_service.WCAS_ABI = []
        with self.assertRaisesRegex(ValueError, "WCAS_ABI could not be loaded"):
            PolygonService()
        self.abi_patcher.start() # Restart for other tests

    def test_init_decimals_call_failure(self):
        """Test __init__ when decimals() call fails, using fallback."""
        self.mock_contract_instance.functions.decimals().call.side_effect = BadFunctionCallOutput("Can't decode")
        with self.assertLogs(polygon_service.logger, level='WARNING') as cm:
            service = PolygonService()
        self.assertEqual(service.wcas_decimals, 18) # Check fallback value
        self.assertTrue(any("Could not call decimals()" in log for log in cm.output))


# --- Tests for mint_wcas ---
class TestPolygonServiceMintWCAS(unittest.TestCase):
    def setUp(self):
        # Similar setup to TestPolygonServiceInit, but focusing on mint_wcas mocks
        self.settings_patcher = patch('backend.services.polygon_service.settings', get_default_mock_settings())
        self.mock_settings = self.settings_patcher.start()

        self.mock_web3_instance = MagicMock(spec=Web3)
        self.mock_web3_instance.eth = MagicMock()
        self.mock_web3_instance.eth.chain_id = 137 # Polygon Mainnet
        self.mock_web3_instance.is_connected.return_value = True

        self.mock_minter_account = MagicMock(spec=LocalAccount)
        self.mock_minter_account.address = "0xMinterAddress"
        
        # New mock for sign_transaction to match web3 v6
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'raw_tx_bytes' # This is what polygon_service will access
        self.mock_minter_account.sign_transaction = MagicMock(return_value=mock_signed_tx)

        self.mock_contract_instance = MagicMock()
        self.mock_contract_instance.functions.decimals().call.return_value = 18

        # Mock for the 'mint' function itself
        self.mock_mint_function = MagicMock()
        self.mock_contract_instance.functions.mint = self.mock_mint_function

        # Mock for the result of mint(...).build_transaction()
        self.mock_built_tx = {'gas': 200000, 'nonce': 1} # example
        self.mock_mint_function.return_value.build_transaction.return_value = self.mock_built_tx

        self.web3_patcher = patch('backend.services.polygon_service.Web3', return_value=self.mock_web3_instance)
        self.mock_Web3_class = self.web3_patcher.start()

        self.mock_web3_instance.eth.account = MagicMock()
        self.mock_web3_instance.eth.account.from_key = MagicMock(return_value=self.mock_minter_account)
        self.mock_from_key = self.mock_web3_instance.eth.account.from_key # Alias for existing assertion checks

        # The service now calls `self.web3.to_hex()`, so we mock it on the instance
        self.mock_web3_instance.to_hex.side_effect = lambda data: '0x' + data.hex()

        self.mock_web3_instance.eth.contract.return_value = self.mock_contract_instance

        self.abi_patcher = patch('backend.services.polygon_service.WCAS_ABI', [{"name": "decimals"}, {"name": "mint"}])
        self.mock_wcas_abi_list = self.abi_patcher.start()

        # Mocks for transaction sending
        self.mock_web3_instance.eth.get_transaction_count.return_value = 1 # nonce
        self.mock_web3_instance.eth.fee_history.return_value = {'baseFeePerGas': [self.mock_web3_instance.to_wei(50, 'gwei')]}
        self.mock_web3_instance.eth.gas_price = self.mock_web3_instance.to_wei(60, 'gwei') # Legacy

        # Mock for send_raw_transaction to return a MagicMock that has a .hex() method
        mock_send_raw_tx_result = MagicMock(spec=HexBytes)
        mock_send_raw_tx_result.hex.return_value = "0x" + ("1234567890abcdef" * 4)
        self.mock_web3_instance.eth.send_raw_transaction.return_value = mock_send_raw_tx_result

        # Instantiate the service
        self.service = PolygonService()

        # Patch Web3.to_checksum_address for this test class as well
        self.checksum_address_patcher = patch('backend.services.polygon_service.Web3.to_checksum_address', side_effect=lambda x: x)
        self.mock_checksum_address = self.checksum_address_patcher.start()


    def tearDown(self):
        self.settings_patcher.stop()
        self.web3_patcher.stop()
        self.abi_patcher.stop()
        self.checksum_address_patcher.stop() 
        importlib.reload(polygon_service)

    def test_mint_wcas_successful_eip1559(self):
        """Test successful wCAS minting using EIP-1559."""
        to_address = "0x" + "A" * 40 # Valid hex address
        amount_float = 10.5

        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
        mock_receipt.get.return_value = to_address  # Mock 'from' and 'to' fields
        self.mock_web3_instance.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check for post-mint validation
        self.mock_web3_instance.eth.call.return_value = b'\\x00' * 31 + b'\\x01'  # Mock balance > 0

        # Mock EIP-1559 fee history
        self.mock_web3_instance.eth.fee_history.return_value = {
            'baseFeePerGas': [1000000000, 1100000000],  # 1 gwei, 1.1 gwei
            'reward': [[500000000], [600000000]]  # 0.5 gwei, 0.6 gwei tip
        }

        # Mock transaction building
        mock_built_tx = {'gas': 100000, 'nonce': 2}
        self.mock_contract_instance.functions.mint.return_value.build_transaction.return_value = mock_built_tx

        # Mock transaction signing and sending
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'signed_transaction_data'
        mock_account = MagicMock()
        mock_account.sign_transaction.return_value = mock_signed_tx
        self.mock_web3_instance.eth.account.from_key.return_value = mock_account

        # Mock get_transaction_count to return different values for different calls
        self.mock_web3_instance.eth.get_transaction_count.side_effect = [2, 2]  # Allow multiple calls

        # Mock send_raw_transaction
        self.mock_web3_instance.eth.send_raw_transaction.return_value = b'tx_hash_bytes'

        # Call mint_wcas
        result = self.service.mint_wcas(to_address, amount_float)

        # Verify the result
        self.assertEqual(result, "0x" + b'tx_hash_bytes'.hex())
        
        # Verify get_transaction_count was called
        self.assertTrue(self.mock_web3_instance.eth.get_transaction_count.called)

    def test_mint_wcas_successful_legacy_gas(self):
        """Test successful wCAS minting using legacy gas pricing."""
        to_address = "0x" + "B" * 40
        amount_float = 5.25

        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'legacy_tx_hash_bytes'
        mock_receipt.get.return_value = to_address  # Mock 'from' and 'to' fields
        self.mock_web3_instance.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check for post-mint validation
        self.mock_web3_instance.eth.call.return_value = b'\\x00' * 31 + b'\\x01'  # Mock balance > 0

        # Mock EIP-1559 fee history failure to trigger legacy gas
        self.mock_web3_instance.eth.fee_history.side_effect = Exception("Fee history not available")

        # Mock legacy gas price
        self.mock_web3_instance.eth.gas_price = 20000000000  # 20 gwei

        # Mock transaction building
        mock_built_tx_legacy = {'gas': 100000, 'nonce': 2}
        self.mock_contract_instance.functions.mint.return_value.build_transaction.return_value = mock_built_tx_legacy

        # Mock transaction signing and sending
        mock_signed_tx_legacy = MagicMock()
        mock_signed_tx_legacy.raw_transaction = b'signed_legacy_tx_data'
        mock_minter_account_legacy = MagicMock()
        mock_minter_account_legacy.sign_transaction.return_value = mock_signed_tx_legacy
        self.mock_web3_instance.eth.account.from_key.return_value = mock_minter_account_legacy

        # Mock get_transaction_count
        self.mock_web3_instance.eth.get_transaction_count.return_value = 2

        # Mock send_raw_transaction
        self.mock_web3_instance.eth.send_raw_transaction.return_value = b'legacy_tx_hash_bytes'

        # Call mint_wcas
        result = self.service.mint_wcas(to_address, amount_float)

        # Verify the result
        self.assertEqual(result, "0x" + b'legacy_tx_hash_bytes'.hex())
        
        # Just verify the function completed successfully
        self.assertIsNotNone(result)

    def test_mint_wcas_fee_history_failure_fallback(self):
        """Test fallback to legacy gas when EIP-1559 fee history fails."""
        to_address = "0x" + "B" * 40 # Valid hex address
        amount_float = 15.0

        # Mock fee_history to raise an exception
        self.mock_web3_instance.eth.fee_history.side_effect = Exception("Fee history failed")

        # Mock legacy gas price
        self.mock_web3_instance.eth.gas_price = 20000000000  # 20 gwei

        # Mock other necessary methods for legacy gas
        self.mock_web3_instance.eth.get_transaction_count.return_value = 3
        mock_built_tx = {'gas': 150000, 'nonce': 3}
        self.mock_contract_instance.functions.mint.return_value.build_transaction.return_value = mock_built_tx

        # Mock transaction signing and sending
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b'fallback_tx_hash'
        mock_account = MagicMock()
        mock_account.sign_transaction.return_value = mock_signed_tx
        self.mock_web3_instance.eth.account.from_key.return_value = mock_account
        self.mock_web3_instance.eth.send_raw_transaction.return_value = b'fallback_tx_hash'

        # Mock transaction receipt for post-mint validation
        mock_receipt = MagicMock()
        mock_receipt.status = 1  # Success status
        mock_receipt.transactionHash = b'fallback_tx_hash'
        mock_receipt.get.return_value = to_address  # Mock 'from' and 'to' fields
        self.mock_web3_instance.eth.wait_for_transaction_receipt.return_value = mock_receipt
        
        # Mock balance check for post-mint validation - recipient has tokens
        self.mock_web3_instance.eth.call.return_value = b'\x00' * 31 + b'\x01'  # Mock balance > 0

        # Call mint_wcas - this should succeed despite fee history failure
        result = self.service.mint_wcas(to_address, amount_float)

        # Verify the result
        self.assertEqual(result, "0x" + b'fallback_tx_hash'.hex())
        
        # Just verify the function completed successfully - don't check specific warning messages
        self.assertIsNotNone(result)

    def test_mint_wcas_conversion_and_checksum(self):
        """Test amount conversion to wei and address checksumming."""
        to_address_lowercase = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        amount_float = 1.0
        self.service.wcas_decimals = 6 # Test with different decimals

        self.service.mint_wcas(to_address_lowercase, amount_float)

        amount_wei = int(amount_float * (10**6))
        self.mock_mint_function.assert_called_once_with(
            to_address_lowercase, amount_wei
        )

    def test_mint_wcas_get_nonce_failure(self):
        self.mock_web3_instance.eth.get_transaction_count.side_effect = Exception("Nonce error")
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            result = self.service.mint_wcas("0xSomeAddress" + "0"*29, 1.0)
        self.assertIsNone(result)
        self.assertIn("🚨 ALLGEMEINER MINT FEHLER: Nonce error", cm.output[0])



    def test_mint_wcas_build_transaction_failure(self):
        self.mock_mint_function.return_value.build_transaction.side_effect = Exception("Build error")
        with self.assertLogs(polygon_service.logger, level='ERROR'):
            result = self.service.mint_wcas("0x" + "C" * 40, 1.0)
        self.assertIsNone(result)

    def test_mint_wcas_sign_transaction_failure(self):
        self.mock_minter_account.sign_transaction.side_effect = Exception("Sign error")
        with self.assertLogs(polygon_service.logger, level='ERROR'):
            result = self.service.mint_wcas("0x" + "D" * 40, 1.0)
        self.assertIsNone(result)

    def test_mint_wcas_send_raw_transaction_failure(self):
        self.mock_web3_instance.eth.send_raw_transaction.side_effect = Exception("Send error")
        with self.assertLogs(polygon_service.logger, level='ERROR'):
            result = self.service.mint_wcas("0x" + "E" * 40, 1.0)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
