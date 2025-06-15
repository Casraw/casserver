import requests
import json
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

class CascoinService:
    def __init__(self):
        self.rpc_url = settings.CASCOIN_RPC_URL
        self.rpc_user = settings.CASCOIN_RPC_USER
        self.rpc_password = settings.CASCOIN_RPC_PASSWORD
        # Ensure RPC URL is correctly formatted
        if not self.rpc_url.startswith("http://") and not self.rpc_url.startswith("https://"):
            self.rpc_url = "http://" + self.rpc_url # Default to http if no scheme

    def _rpc_call(self, method: str, params: list = None):
        if params is None:
            params = []
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": "cascoin_service_rpc",
            "method": method,
            "params": params
        })
        auth = (self.rpc_user, self.rpc_password)
        headers = {'Content-Type': 'application/json'}

        logger.debug(f"Calling Cascoin RPC method: {method} with params: {params} to URL: {self.rpc_url}")

        try:
            response = requests.post(self.rpc_url, auth=auth, data=payload, headers=headers, timeout=10)
            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
            data = response.json()
            if data.get("error"):
                logger.error(f"Cascoin RPC error for method {method}: {data['error']}")
                return None
            return data.get("result")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling Cascoin RPC method {method} at {self.rpc_url}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error calling Cascoin RPC method {method} at {self.rpc_url}. Ensure Cascoin daemon is running and accessible.")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error calling Cascoin RPC method {method}: {e}. Response: {e.response.text if e.response else 'No response text'}")
            return None
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response from Cascoin RPC method {method}. Response: {response.text if 'response' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Generic error in Cascoin RPC call for method {method}: {e}", exc_info=True)
            return None

    def get_new_address(self, account: str = "") -> str | None:
        """
        Generates a new Cascoin address.
        Bitcoin Core uses an optional 'label' (formerly 'account') for `getnewaddress`.
        If Cascoin's `getnewaddress` doesn't use/need an account/label, params can be empty.
        Adjust params if Cascoin's RPC call for a new address differs.
        For now, assuming `getnewaddress` with an optional label/account string.
        If Cascoin does not use an account/label for getnewaddress, the `params` list should be empty.
        Let's assume for now that an empty string for account is fine if not used, or it refers to the default account.
        """
        params = [account] if account else [] # Pass account if provided, else empty list for default
        # If Cascoin's getnewaddress strictly requires no params for default, use:
        # params = []
        # If it requires a label and "" is not a valid default label, this might need adjustment
        # based on actual Cascoin RPC specifics.

        address = self._rpc_call("getnewaddress", params)
        if address and isinstance(address, str):
            logger.info(f"Successfully generated new Cascoin address: {address}")
            return address
        else:
            logger.error(f"Failed to generate new Cascoin address or address format is incorrect. Received: {address}")
            return None

    def get_blockchain_info(self): # Example utility function
        """Gets basic blockchain information from the Cascoin node."""
        info = self._rpc_call("getblockchaininfo")
        if info:
            logger.info(f"Cascoin blockchain info: {info.get('chain')}, blocks: {info.get('blocks')}")
        return info

    def send_cas(self, to_address: str, amount: float) -> str | None:
        """
        Sends CAS to a specified address using the Cascoin node's RPC.
        Assumes the wallet has sufficient funds and is unlocked if necessary.
        RPC command is typically 'sendtoaddress'.
        """
        # Validate amount to prevent issues like sending zero or negative amounts
        if amount <= 0:
            logger.error(f"Invalid amount for send_cas: {amount}. Must be positive.")
            return None

        # Basic address validation (very simple, Cascoin node will do the real check)
        if not to_address or len(to_address) < 20: # Arbitrary min length, can be improved
            logger.error(f"Invalid to_address for send_cas: '{to_address}'")
            return None

        params = [to_address, float(amount)] # Ensure amount is float for JSON-RPC
        logger.info(f"Attempting to send {amount} CAS to {to_address} via RPC.")

        txid = self._rpc_call("sendtoaddress", params)

        if txid and isinstance(txid, str) and len(txid) == 64 : # Basic check for hex txid format
            logger.info(f"Successfully sent {amount} CAS to {to_address}. Transaction ID: {txid}")
            return txid
        else:
            # _rpc_call should log specific RPC errors.
            # This logs the failure at the service method level.
            logger.error(f"Failed to send CAS to {to_address}. Received from RPC call: {txid}")
            if txid is None: # RPC call itself failed (e.g. connection, timeout, RPC error object from node)
                logger.error("This could be due to RPC errors (check previous logs from _rpc_call), insufficient funds, or an invalid address not caught by basic checks.")
            elif not isinstance(txid, str):
                 logger.error(f"Expected a string transaction ID, but got type {type(txid)}.")
            elif len(txid) != 64:
                 logger.error(f"Expected 64-character hex transaction ID, but got length {len(txid)}.")
            return None

# Example usage (for testing purposes, not part of the service directly)
if __name__ == '__main__':
    # This part would require backend.config to be loadable,
    # which might need environment variables (like DATABASE_URL at least)
    # For simple testing, you might need to mock settings or ensure .env is present
    print("Attempting to initialize CascoinService and test connection...")

    # Setup basic logging for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Ensure environment variables for Cascoin RPC are set if you run this directly
    # e.g., CASCOIN_RPC_URL, CASCOIN_RPC_USER, CASCOIN_RPC_PASSWORD
    # and a dummy DATABASE_URL in .env for settings to load without error

    # A simple way to test if settings load (might fail if .env isn't right for other settings)
    try:
        print(f"Attempting to use CASCOIN_RPC_URL: {settings.CASCOIN_RPC_URL}")
    except Exception as e:
        print(f"Could not load settings, ensure .env is configured correctly for backend.config: {e}")
        print("Skipping direct CascoinService test.")
        exit()

    service = CascoinService()
    blockchain_info = service.get_blockchain_info()
    if blockchain_info:
        print("Successfully connected to Cascoin node and got blockchain info.")
        new_address = service.get_new_address("test_label") # Using a label
        if new_address:
            print(f"Generated new Cascoin address: {new_address}")
        else:
            print("Failed to generate new Cascoin address.")

        # Test getnewaddress without a label (for default account)
        # default_address = service.get_new_address()
        # if default_address:
        #     print(f"Generated new Cascoin address (default account): {default_address}")
        # else:
        #     print("Failed to generate new Cascoin address (default account).")
    else:
        print("Failed to connect to Cascoin node or get blockchain info. Check RPC settings and daemon status.")
