import unittest
from unittest.mock import patch, MagicMock, mock_open
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

# --- Helper for settings mock ---
def get_default_mock_settings():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.POLYGON_RPC_URL = "https://mockrpc.com"
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

        self.from_key_patcher = patch('web3.eth.account.Account.from_key', return_value=self.mock_minter_account)
        self.mock_from_key = self.from_key_patcher.start()

        # Mock the contract call within the Web3 instance
        self.mock_web3_instance.eth.contract.return_value = self.mock_contract_instance

        # Mock WCAS_ABI at module level for init tests
        self.abi_patcher = patch('backend.services.polygon_service.WCAS_ABI', [{"name": "decimals"}]) # Minimal valid ABI
        self.mock_wcas_abi_list = self.abi_patcher.start()


    def tearDown(self):
        self.settings_patcher.stop()
        self.web3_patcher.stop()
        self.from_key_patcher.stop()
        self.abi_patcher.stop()
        # Important: reload the module to reset its global WCAS_ABI state after ABI tests
        importlib.reload(polygon_service)


    def test_init_successful(self):
        """Test successful initialization of PolygonService."""
        service = PolygonService()

        self.mock_Web3_class.HTTPProvider.assert_called_once_with(self.mock_settings.POLYGON_RPC_URL, request_kwargs={'timeout': 60})
        self.mock_web3_instance.middleware_onion.inject.assert_called_once() # Assuming default URL matches polygon
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
        """Test __init__ with a placeholder MINTER_PRIVATE_KEY (should log error but not raise if service allows)."""
        self.mock_settings.MINTER_PRIVATE_KEY = "0x" + "0" * 64
        # PolygonService logs an error but might not raise if designed to allow some read-only ops
        # Current PolygonService raises ValueError if from_key fails, this test is similar to invalid key
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
             with self.assertRaisesRegex(ValueError, "Invalid or missing MINTER_PRIVATE_KEY"): # Assuming it still raises due to from_key
                PolygonService()
        # Check for the specific log about placeholder if from_key didn't raise first
        # This depends on precise error handling order in PolygonService
        # self.assertIn("MINTER_PRIVATE_KEY is a placeholder", cm.output[0])


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
        self.abi_patcher.stop() # Stop the current patch
        self.abi_patcher = patch('backend.services.polygon_service.WCAS_ABI', []) # Patch with empty list
        self.mock_wcas_abi_list = self.abi_patcher.start()

        with self.assertRaisesRegex(ValueError, "WCAS_ABI could not be loaded."):
            PolygonService()

    def test_init_decimals_call_failure(self):
        """Test __init__ when decimals() call fails on contract, uses fallback."""
        self.mock_contract_instance.functions.decimals().call.side_effect = BadFunctionCallOutput("Decimals call failed")

        with self.assertLogs(polygon_service.logger, level='WARNING') as cm:
            service = PolygonService()

        self.assertEqual(service.wcas_decimals, 18) # Fallback value
        self.assertIn("Could not call decimals() on wCAS contract.", cm.output[0])
        self.assertIn("Assuming 18 decimals", cm.output[0])

# Placeholder for mint_wcas tests - to be implemented next
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
        self.mock_minter_account.sign_transaction = MagicMock(return_value=MagicMock(rawTransaction=b'raw_tx_bytes'))

        self.mock_contract_instance = MagicMock()
        self.mock_contract_instance.functions.decimals().call.return_value = 18
        # Mock for mint().build_transaction()
        self.mock_built_tx = {'gas': 200000, 'nonce': 1} # example
        self.mock_contract_instance.functions.mint().build_transaction.return_value = self.mock_built_tx

        self.web3_patcher = patch('backend.services.polygon_service.Web3', return_value=self.mock_web3_instance)
        self.mock_Web3_class = self.web3_patcher.start()

        self.from_key_patcher = patch('web3.eth.account.Account.from_key', return_value=self.mock_minter_account)
        self.mock_from_key = self.from_key_patcher.start()

        self.mock_web3_instance.eth.contract.return_value = self.mock_contract_instance

        self.abi_patcher = patch('backend.services.polygon_service.WCAS_ABI', [{"name": "decimals"}, {"name": "mint"}])
        self.mock_wcas_abi_list = self.abi_patcher.start()

        # Mocks for transaction sending
        self.mock_web3_instance.eth.get_transaction_count.return_value = 1 # nonce
        self.mock_web3_instance.eth.fee_history.return_value = {'baseFeePerGas': [self.mock_web3_instance.to_wei(50, 'gwei')]}
        self.mock_web3_instance.eth.gas_price = self.mock_web3_instance.to_wei(60, 'gwei') # Legacy
        self.mock_web3_instance.eth.send_raw_transaction.return_value = bytes.fromhex("1234567890abcdef" * 4) # Mock tx hash

        # Instantiate the service
        self.service = PolygonService()


    def tearDown(self):
        self.settings_patcher.stop()
        self.web3_patcher.stop()
        self.from_key_patcher.stop()
        self.abi_patcher.stop()
        importlib.reload(polygon_service)

    def test_mint_wcas_successful_eip1559(self):
        """Test successful wCAS minting using EIP-1559."""
        to_address = "0xRecipientAddress" + "0" * (40 - len("0xRecipientAddress"))
        amount_float = 10.5

        expected_tx_hash = "0x" + ("1234567890abcdef" * 4)
        tx_hash = self.service.mint_wcas(to_address, amount_float)

        self.assertEqual(tx_hash, expected_tx_hash)
        self.mock_web3_instance.eth.get_transaction_count.assert_called_once_with(self.service.minter_address)
        self.mock_web3_instance.eth.fee_history.assert_called_once() # For EIP-1559

        amount_wei = int(amount_float * (10**self.service.wcas_decimals))
        self.service.wcas_contract.functions.mint.assert_called_once_with(
            Web3.to_checksum_address(to_address), amount_wei
        )

        # Check that build_transaction was called with EIP-1559 params
        # args, kwargs = self.service.wcas_contract.functions.mint().build_transaction.call_args
        # self.assertIn('maxFeePerGas', kwargs[0])
        # self.assertIn('maxPriorityFeePerGas', kwargs[0])
        # self.assertEqual(kwargs[0]['type'], '0x2')
        # More detailed check of build_transaction args if necessary:
        build_tx_call_args = self.service.wcas_contract.functions.mint().build_transaction.call_args[0][0]
        self.assertEqual(build_tx_call_args['from'], self.service.minter_address)
        self.assertEqual(build_tx_call_args['nonce'], 1)
        self.assertIn('maxFeePerGas', build_tx_call_args)
        self.assertIn('maxPriorityFeePerGas', build_tx_call_args)


        self.service.minter_account.sign_transaction.assert_called_once_with(self.mock_built_tx)
        self.mock_web3_instance.eth.send_raw_transaction.assert_called_once_with(b'raw_tx_bytes')


    def test_mint_wcas_successful_legacy_gas(self):
        """Test successful wCAS minting using legacy gas price."""
        self.service.chain_id = 1 # Simulate non-EIP1559 chain (e.g., Ethereum mainnet before London)
        # Re-init service or directly set chain_id for this test
        # For simplicity, directly modify service's chain_id if PolygonService allows it,
        # or re-initialize with a mock Web3 having different chain_id.
        # Here, we'll assume self.service.chain_id can be changed for test purposes.
        # Note: A cleaner way is to re-initialize service with specific mock for chain_id

        # To properly test this, we need to re-initialize the service with a different chain_id
        # This requires a bit more setup for this specific test case.
        # Let's mock the chain_id attribute of the web3 instance used by a fresh service instance.

        mock_settings_legacy = get_default_mock_settings()
        mock_web3_legacy = MagicMock(spec=Web3)
        mock_web3_legacy.eth = MagicMock()
        mock_web3_legacy.eth.chain_id = 1 # Non-EIP1559 chain
        mock_web3_legacy.is_connected.return_value = True
        mock_web3_legacy.eth.contract.return_value = self.mock_contract_instance # reuse contract mock
        mock_web3_legacy.eth.get_transaction_count.return_value = 2 # new nonce
        mock_web3_legacy.eth.gas_price = self.mock_web3_instance.to_wei(70, 'gwei') # Legacy gas price

        with patch('backend.services.polygon_service.Web3', return_value=mock_web3_legacy), \
             patch('backend.services.polygon_service.settings', mock_settings_legacy), \
             patch('web3.eth.account.Account.from_key', return_value=self.mock_minter_account), \
             patch('backend.services.polygon_service.WCAS_ABI', self.mock_wcas_abi_list):
            legacy_service = PolygonService()
            legacy_service.wcas_contract.functions.mint().build_transaction.return_value = {'gas': 100000, 'nonce': 2} # new built tx
            self.mock_minter_account.sign_transaction.return_value = MagicMock(rawTransaction=b'legacy_raw_tx')


            to_address = "0xLegacyRecipient" + "0" * (40 - len("0xLegacyRecipient"))
            amount_float = 5.0
            expected_tx_hash = "0x" + ("1234567890abcdef" * 4) # send_raw_transaction still returns this from outer scope mock

            tx_hash = legacy_service.mint_wcas(to_address, amount_float)

            self.assertEqual(tx_hash, expected_tx_hash)
            mock_web3_legacy.eth.fee_history.assert_not_called() # EIP-1559 should not be called
            mock_web3_legacy.eth.gas_price_get_call_count = legacy_service.web3.eth.gas_price.call_count # call_count for property

            # Check build_transaction was called with legacy gasPrice
            build_tx_call_args = legacy_service.wcas_contract.functions.mint().build_transaction.call_args[0][0]
            self.assertIn('gasPrice', build_tx_call_args)
            self.assertEqual(build_tx_call_args['gasPrice'], mock_web3_legacy.eth.gas_price)
            self.assertNotIn('maxFeePerGas', build_tx_call_args)
            self.assertNotIn('maxPriorityFeePerGas', build_tx_call_args)

            self.mock_minter_account.sign_transaction.assert_called_with({'gas': 100000, 'nonce': 2})
            mock_web3_legacy.eth.send_raw_transaction.assert_called_once_with(b'legacy_raw_tx')


    def test_mint_wcas_conversion_and_checksum(self):
        """Test amount conversion to wei and address checksumming."""
        to_address = "0xrecipientaddress" + "0" * (40 - len("0xrecipientaddress")) # Non-checksummed
        amount_float = 1.0
        self.service.wcas_decimals = 6 # Test with different decimals

        self.service.mint_wcas(to_address, amount_float)

        amount_wei = int(amount_float * (10**6))
        self.service.wcas_contract.functions.mint.assert_called_once_with(
            Web3.to_checksum_address(to_address), amount_wei
        )

    # --- Failure point tests for mint_wcas ---
    def test_mint_wcas_get_nonce_failure(self):
        self.mock_web3_instance.eth.get_transaction_count.side_effect = Exception("Nonce error")
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            result = self.service.mint_wcas("0xSomeAddress" + "0"*29, 1.0)
        self.assertIsNone(result)
        self.assertIn("Error minting wCAS: Nonce error", cm.output[0])

    def test_mint_wcas_fee_history_failure_fallback(self):
        """Test EIP-1559 fee history failure, falling back to legacy gas and succeeding."""
        self.mock_web3_instance.eth.fee_history.side_effect = Exception("Fee history error")
        # Ensure legacy gas price is used and succeeds
        self.mock_web3_instance.eth.gas_price = self.mock_web3_instance.to_wei(60, 'gwei')

        with self.assertLogs(polygon_service.logger, level='WARNING') as cm_warning: # For fallback log
             with self.assertLogs(polygon_service.logger, level='INFO') as cm_info: # For success log
                tx_hash = self.service.mint_wcas("0xSomeAddress" + "0"*29, 1.0)

        self.assertIsNotNone(tx_hash) # Should succeed using legacy
        self.assertIn("Could not determine EIP-1559 fees, falling back to legacy gasPrice", cm_warning.output[0])

        # Check that build_transaction was called with legacy gasPrice
        build_tx_call_args = self.service.wcas_contract.functions.mint().build_transaction.call_args[0][0]
        self.assertIn('gasPrice', build_tx_call_args)
        self.assertEqual(build_tx_call_args['gasPrice'], self.mock_web3_instance.eth.gas_price)

    def test_mint_wcas_build_transaction_failure(self):
        self.service.wcas_contract.functions.mint().build_transaction.side_effect = Exception("Build tx error")
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            result = self.service.mint_wcas("0xSomeAddress" + "0"*29, 1.0)
        self.assertIsNone(result)
        self.assertIn("Error minting wCAS: Build tx error", cm.output[0])

    def test_mint_wcas_sign_transaction_failure(self):
        self.mock_minter_account.sign_transaction.side_effect = Exception("Sign error")
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            result = self.service.mint_wcas("0xSomeAddress" + "0"*29, 1.0)
        self.assertIsNone(result)
        self.assertIn("Error minting wCAS: Sign error", cm.output[0])

    def test_mint_wcas_send_raw_transaction_failure(self):
        self.mock_web3_instance.eth.send_raw_transaction.side_effect = Exception("Send error")
        with self.assertLogs(polygon_service.logger, level='ERROR') as cm:
            result = self.service.mint_wcas("0xSomeAddress" + "0"*29, 1.0)
        self.assertIsNone(result)
        self.assertIn("Error minting wCAS: Send error", cm.output[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)

# Note: Some tests for mint_wcas might need more specific argument checking for build_transaction
# depending on how gas parameters are structured and passed.
# The current PolygonService has a specific structure for EIP-1559 and legacy gas.
# Test test_mint_wcas_successful_eip1559 and test_mint_wcas_successful_legacy_gas attempt to cover this.
# Test test_mint_wcas_fee_history_failure_fallback checks the fallback mechanism.
# More permutations (e.g. EIP-1559 fails and legacy gas price also fails) could be added if necessary.
