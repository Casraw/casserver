import unittest
from unittest.mock import patch, MagicMock
import json # For mocking JSON responses

# Modules to test
from backend.services.cascoin_service import CascoinService
from backend.config import Settings # To mock settings

# To mock requests.post and its exceptions
import requests

class TestCascoinService(unittest.TestCase):

    @patch('backend.services.cascoin_service.settings')
    def test_init_default_url_scheme(self, mock_settings):
        """Test that RPC URL is prefixed with http:// if no scheme is provided."""
        mock_settings.CASCOIN_RPC_URL = "localhost:18332"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        service = CascoinService()
        self.assertEqual(service.rpc_url, "http://localhost:18332")
        self.assertEqual(service.rpc_user, "testuser")
        self.assertEqual(service.rpc_password, "testpass")

    @patch('backend.services.cascoin_service.settings')
    def test_init_with_http_scheme(self, mock_settings):
        """Test that RPC URL is used as is if http:// scheme is provided."""
        mock_settings.CASCOIN_RPC_URL = "http://somehost:1234"
        mock_settings.CASCOIN_RPC_USER = "user1"
        mock_settings.CASCOIN_RPC_PASSWORD = "pass1"

        service = CascoinService()
        self.assertEqual(service.rpc_url, "http://somehost:1234")

    @patch('backend.services.cascoin_service.settings')
    def test_init_with_https_scheme(self, mock_settings):
        """Test that RPC URL is used as is if https:// scheme is provided."""
        mock_settings.CASCOIN_RPC_URL = "https://securehost:5678"
        mock_settings.CASCOIN_RPC_USER = "user2"
        mock_settings.CASCOIN_RPC_PASSWORD = "pass2"

        service = CascoinService()
        self.assertEqual(service.rpc_url, "https://securehost:5678")

    # --- Tests for _rpc_call ---
    # We will test _rpc_call indirectly via public methods,
    # but these setup mocks for requests.post that _rpc_call uses.

    @patch('backend.services.cascoin_service.requests.post')
    @patch('backend.services.cascoin_service.settings')
    def test_rpc_call_successful(self, mock_settings, mock_post):
        """Test a successful RPC call."""
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        # Configure mock_post
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success_data", "error": None, "id": "cascoin_service_rpc"}
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock() # Ensure it doesn't raise for 200
        mock_post.return_value = mock_response

        service = CascoinService()
        result = service._rpc_call(method="testmethod", params=[1, 2])

        self.assertEqual(result, "success_data")
        mock_post.assert_called_once_with(
            "http://testurl",
            auth=("testuser", "testpass"),
            data=json.dumps({
                "jsonrpc": "2.0",
                "id": "cascoin_service_rpc",
                "method": "testmethod",
                "params": [1, 2]
            }),
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        mock_response.raise_for_status.assert_called_once()

    @patch('backend.services.cascoin_service.requests.post')
    @patch('backend.services.cascoin_service.settings')
    def test_rpc_call_node_error(self, mock_settings, mock_post):
        """Test RPC call when the node returns an error in the JSON response."""
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        mock_response = MagicMock()
        mock_response.json.return_value = {"result": None, "error": {"code": -1, "message": "Node error"}, "id": "cascoin_service_rpc"}
        mock_response.status_code = 200 # Or 500, node might return error within a 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            result = service._rpc_call(method="errormethod")

        self.assertIsNone(result)
        self.assertIn("Cascoin RPC error for method errormethod: {'code': -1, 'message': 'Node error'}", cm.output[0])

    @patch('backend.services.cascoin_service.requests.post')
    @patch('backend.services.cascoin_service.settings')
    def test_rpc_call_timeout(self, mock_settings, mock_post):
        """Test RPC call with requests.exceptions.Timeout."""
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            result = service._rpc_call(method="timeoutmethod")

        self.assertIsNone(result)
        self.assertIn("Timeout calling Cascoin RPC method timeoutmethod at http://testurl", cm.output[0])

    @patch('backend.services.cascoin_service.requests.post')
    @patch('backend.services.cascoin_service.settings')
    def test_rpc_call_connection_error(self, mock_settings, mock_post):
        """Test RPC call with requests.exceptions.ConnectionError."""
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            result = service._rpc_call(method="connecterrormethod")

        self.assertIsNone(result)
        self.assertIn("Connection error calling Cascoin RPC method connecterrormethod at http://testurl", cm.output[0])

    @patch('backend.services.cascoin_service.requests.post')
    @patch('backend.services.cascoin_service.settings')
    def test_rpc_call_http_error(self, mock_settings, mock_post):
        """Test RPC call with requests.exceptions.HTTPError."""
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        mock_http_error_response = MagicMock()
        mock_http_error_response.text = "Internal Server Error"
        mock_post.side_effect = requests.exceptions.HTTPError(response=mock_http_error_response)

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            result = service._rpc_call(method="httperrormethod")

        self.assertIsNone(result)
        self.assertIn("HTTP error calling Cascoin RPC method httperrormethod", cm.output[0])
        self.assertIn("Response: Internal Server Error", cm.output[0])

    @patch('backend.services.cascoin_service.requests.post')
    @patch('backend.services.cascoin_service.settings')
    def test_rpc_call_json_decode_error(self, mock_settings, mock_post):
        """Test RPC call with json.JSONDecodeError."""
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "testuser"
        mock_settings.CASCOIN_RPC_PASSWORD = "testpass"

        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        mock_response.text = "Invalid JSON" # Text to be logged
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            result = service._rpc_call(method="jsonerrormethod")

        self.assertIsNone(result)
        self.assertIn("Failed to decode JSON response from Cascoin RPC method jsonerrormethod. Response: Invalid JSON", cm.output[0])

    # --- Tests for get_new_address ---
    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings') # Still need to mock settings for __init__
    def test_get_new_address_success(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl" # Basic settings for init
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        expected_address = "newcascoinaddress123"
        mock_rpc_call.return_value = expected_address

        service = CascoinService()
        address = service.get_new_address(account="test_account")

        self.assertEqual(address, expected_address)
        mock_rpc_call.assert_called_once_with("getnewaddress", ["test_account"])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_get_new_address_success_no_account(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        expected_address = "defaultaddress456"
        mock_rpc_call.return_value = expected_address

        service = CascoinService()
        address = service.get_new_address() # No account parameter

        self.assertEqual(address, expected_address)
        mock_rpc_call.assert_called_once_with("getnewaddress", []) # Expects empty list for params

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_get_new_address_rpc_error(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        mock_rpc_call.return_value = None # Simulate RPC error

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            address = service.get_new_address(account="test_account")

        self.assertIsNone(address)
        self.assertIn("Failed to generate new Cascoin address or address format is incorrect. Received: None", cm.output[0])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_get_new_address_invalid_return_type(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        mock_rpc_call.return_value = {"address": "not_a_string_address"} # Simulate incorrect return type

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            address = service.get_new_address()

        self.assertIsNone(address)
        self.assertIn("Failed to generate new Cascoin address or address format is incorrect. Received: {'address': 'not_a_string_address'}", cm.output[0])


    # --- Tests for send_cas ---
    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_success(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        expected_txid = ("0123456789abcdef" * 4) # 64 char hex string
        mock_rpc_call.return_value = expected_txid

        service = CascoinService()
        txid = service.send_cas(to_address="validcasaddress_longenough", amount=10.5)

        self.assertEqual(txid, expected_txid)
        mock_rpc_call.assert_called_once_with("sendtoaddress", ["validcasaddress_longenough", 10.5])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_rpc_error(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        mock_rpc_call.return_value = None # Simulate RPC error

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="validcasaddress_longenough", amount=5.0)

        self.assertIsNone(txid)
        self.assertIn("Failed to send CAS to validcasaddress_longenough. Received from RPC call: None", cm.output[0])
        self.assertIn("This could be due to RPC errors", cm.output[1])


    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_invalid_amount_zero(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="validcasaddress", amount=0)

        self.assertIsNone(txid)
        mock_rpc_call.assert_not_called()
        self.assertIn("Invalid amount for send_cas: 0. Must be positive.", cm.output[0])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_invalid_amount_negative(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="validcasaddress", amount=-1.0)

        self.assertIsNone(txid)
        mock_rpc_call.assert_not_called()
        self.assertIn("Invalid amount for send_cas: -1.0. Must be positive.", cm.output[0])


    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_invalid_address_empty(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="", amount=10.0)

        self.assertIsNone(txid)
        mock_rpc_call.assert_not_called()
        self.assertIn("Invalid to_address for send_cas: ''", cm.output[0])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_invalid_address_short(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="short", amount=10.0)

        self.assertIsNone(txid)
        mock_rpc_call.assert_not_called()
        self.assertIn("Invalid to_address for send_cas: 'short'", cm.output[0])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_invalid_txid_type(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        mock_rpc_call.return_value = 12345 # Not a string txid

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="validcasaddress_longenough", amount=5.0)

        self.assertIsNone(txid)
        self.assertIn("Failed to send CAS to validcasaddress_longenough. Received from RPC call: 12345", cm.output[0])
        self.assertIn("Expected a string transaction ID, but got type <class 'int'>.", cm.output[1])

    @patch.object(CascoinService, '_rpc_call')
    @patch('backend.services.cascoin_service.settings')
    def test_send_cas_invalid_txid_length(self, mock_settings, mock_rpc_call):
        mock_settings.CASCOIN_RPC_URL = "http://testurl"
        mock_settings.CASCOIN_RPC_USER = "user"
        mock_settings.CASCOIN_RPC_PASSWORD = "password"

        mock_rpc_call.return_value = "short_txid" # Invalid length

        service = CascoinService()
        with self.assertLogs('backend.services.cascoin_service', level='ERROR') as cm:
            txid = service.send_cas(to_address="validcasaddress_longenough", amount=5.0)

        self.assertIsNone(txid)
        self.assertIn("Failed to send CAS to validcasaddress_longenough. Received from RPC call: short_txid", cm.output[0])
        self.assertIn("Expected 64-character hex transaction ID, but got length 10.", cm.output[1])

if __name__ == '__main__':
    unittest.main()
