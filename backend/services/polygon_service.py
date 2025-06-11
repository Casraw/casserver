import json
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from backend.config import settings
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

WCAS_ABI = []
ABI_FILE_PATH = settings.WCAS_CONTRACT_ABI_JSON_PATH

# Try to resolve path relative to the project root (common case)
# Assumes 'backend' and 'smart_contracts' are siblings in the project root.
project_root_abi_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ABI_FILE_PATH)

if os.path.exists(ABI_FILE_PATH): # Check original path first (e.g. if absolute or run from root)
    pass
elif os.path.exists(project_root_abi_path): # Check path relative to project root
    ABI_FILE_PATH = project_root_abi_path
else:
    logger.warning(f"ABI file not found at original path {ABI_FILE_PATH} or project root relative path {project_root_abi_path}.")

if os.path.exists(ABI_FILE_PATH):
    try:
        with open(ABI_FILE_PATH, 'r') as f:
            WCAS_ABI = json.load(f)
        logger.info(f"Successfully loaded wCAS ABI from {ABI_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error loading ABI from {ABI_FILE_PATH}: {e}", exc_info=True)
else:
    logger.error(f"ABI file not found at {ABI_FILE_PATH}. Critical for PolygonService.")


class PolygonService:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL, request_kwargs={'timeout': 60}))

        if "mumbai" in settings.POLYGON_RPC_URL.lower() or "matic" in settings.POLYGON_RPC_URL.lower() or "polygon" in settings.POLYGON_RPC_URL.lower():
             self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
             logger.info("Injected PoA middleware for Polygon.")

        if not self.web3.is_connected(): # Removed show_traceback
            logger.error(f"Failed to connect to Polygon node at {settings.POLYGON_RPC_URL}")
            raise ConnectionError(f"Failed to connect to Polygon node at {settings.POLYGON_RPC_URL}")

        self.chain_id = self.web3.eth.chain_id
        logger.info(f"Connected to Polygon node: {settings.POLYGON_RPC_URL}. Chain ID: {self.chain_id}")

        if settings.MINTER_PRIVATE_KEY == "0x0000000000000000000000000000000000000000000000000000000000000000":
            logger.error("MINTER_PRIVATE_KEY is a placeholder. Real key required for minting.")
            # raise ValueError("MINTER_PRIVATE_KEY is a placeholder.") # Can choose to raise or allow service to init for read-only calls
        try:
            self.minter_account = self.web3.eth.account.from_key(settings.MINTER_PRIVATE_KEY)
            self.minter_address = self.minter_account.address
            logger.info(f"Using Minter Address: {self.minter_address}")
        except Exception as e: # Catch specific exceptions if possible
            logger.error(f"Invalid MINTER_PRIVATE_KEY: {e}", exc_info=True)
            raise ValueError(f"Invalid or missing MINTER_PRIVATE_KEY: {e}")

        if not settings.WCAS_CONTRACT_ADDRESS or settings.WCAS_CONTRACT_ADDRESS == "0x0000000000000000000000000000000000000000":
             logger.error("WCAS_CONTRACT_ADDRESS is not set or is a placeholder.")
             raise ValueError("WCAS_CONTRACT_ADDRESS is not configured properly.")

        if not WCAS_ABI: # ABI loading failed
            logger.error("WCAS_ABI is not loaded. Cannot initialize contract.")
            raise ValueError("WCAS_ABI could not be loaded. Check path and file content.")

        self.wcas_contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(settings.WCAS_CONTRACT_ADDRESS),
            abi=WCAS_ABI
        )
        logger.info(f"wCAS Contract object initialized for address: {self.wcas_contract.address}")

        try:
            # Test contract connection if ABI is sufficient
            self.wcas_decimals = self.wcas_contract.functions.decimals().call()
            logger.info(f"wCAS contract decimals from chain: {self.wcas_decimals}")
        except Exception as e:
            logger.warning(f"Could not call decimals() on wCAS contract. ABI might be incorrect or contract not deployed/verified: {e}. Assuming 18 decimals.")
            self.wcas_decimals = 18 # Fallback, risky.

    def mint_wcas(self, to_address: str, amount_cas_float: float) -> Optional[str]:
        try:
            amount_wei = int(amount_cas_float * (10**self.wcas_decimals))
            logger.info(f"Attempting to mint {amount_wei} wCAS ({amount_cas_float} CAS equiv. using {self.wcas_decimals} decimals) to {to_address}")

            checksum_to_address = Web3.to_checksum_address(to_address)
            nonce = self.web3.eth.get_transaction_count(self.minter_address)

            tx_params = {'from': self.minter_address, 'nonce': nonce, 'gas': settings.DEFAULT_GAS_LIMIT}

            if self.chain_id in [137, 80001]: # Polygon Mainnet or Mumbai
                try:
                    fee_history = self.web3.eth.fee_history(1, 'latest', [25])
                    base_fee_per_gas = fee_history['baseFeePerGas'][-1]
                    max_priority_fee_per_gas = self.web3.to_wei(settings.DEFAULT_MAX_PRIORITY_FEE_PER_GAS_GWEI, 'gwei')
                    max_fee_per_gas = base_fee_per_gas + max_priority_fee_per_gas

                    tx_params.update({
                        'maxPriorityFeePerGas': max_priority_fee_per_gas,
                        'maxFeePerGas': max_fee_per_gas,
                        'type': '0x2'
                    })
                    logger.info(f"Using EIP-1559 tx params: maxFeePerGas={max_fee_per_gas}, maxPriorityFeePerGas={max_priority_fee_per_gas}")
                except Exception as e:
                    logger.warning(f"Could not determine EIP-1559 fees, falling back to legacy gasPrice: {e}")
                    tx_params['gasPrice'] = self.web3.eth.gas_price
            else: # Other chains or if EIP-1559 fails
                tx_params['gasPrice'] = self.web3.eth.gas_price

            logger.debug(f"Transaction parameters for minting: {tx_params}")

            transaction = self.wcas_contract.functions.mint(checksum_to_address, amount_wei).build_transaction(tx_params)
            signed_tx = self.minter_account.sign_transaction(transaction)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"wCAS mint transaction sent. Hash: {tx_hash.hex()}.")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Error minting wCAS: {e}", exc_info=True)
            return None
