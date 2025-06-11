import time
import json
import requests # For making HTTP requests to backend and Cascoin RPC
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData
from sqlalchemy.orm import sessionmaker, Session as DbSession # Renamed to avoid conflict
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
CASCOIN_RPC_URL = "http://localhost:18332" # Example Cascoin RPC URL
CASCOIN_RPC_USER = "your_cascoin_rpc_user"
CASCOIN_RPC_PASSWORD = "your_cascoin_rpc_password"
BRIDGE_API_URL = "http://localhost:8000/api" # Backend API
DATABASE_URL = "sqlite:///./bridge.db" # Must match backend's DB
POLL_INTERVAL_SECONDS = 60
CONFIRMATIONS_REQUIRED = 6

# --- Database Setup ---
# The watcher accesses the DB directly. Ensure it uses the same bridge.db file.
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define the CasDeposit model (mirroring database.models.CasDeposit)
# This is to avoid direct dependency on backend code structure for this separate process.
# A shared library or schema definition would be better in a larger project.
Base = declarative_base()

class CasDeposit(Base):
    __tablename__ = "cas_deposits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    polygon_address = Column(String, index=True, nullable=False)
    cascoin_deposit_address = Column(String, unique=True, index=True, nullable=False)
    received_amount = Column(Float, nullable=True)
    status = Column(String, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    mint_tx_hash = Column(String, nullable=True)

    def __repr__(self):
        return f"<CasDeposit(id={self.id}, cas_addr='{self.cascoin_deposit_address}', status='{self.status}')>"

# --- Cascoin JSON-RPC Interaction ---
def cascoin_rpc_call(method, params=[]):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": "cascoin_watcher",
        "method": method,
        "params": params
    })
    try:
        response = requests.post(
            CASCOIN_RPC_URL,
            auth=(CASCOIN_RPC_USER, CASCOIN_RPC_PASSWORD),
            data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10 # Added timeout
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout calling Cascoin RPC {method}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Cascoin RPC {method}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding Cascoin RPC response for {method}. Response: {response.text if 'response' in locals() else 'N/A'}")
        return None

# --- Backend API Interaction (Placeholder for Minting Trigger) ---
def trigger_wcas_minting(deposit_id: int, amount: float, target_polygon_address: str, cas_deposit_address: str):
    logger.info(f"Attempting to trigger wCAS minting for CasDeposit ID: {deposit_id}, Amount: {amount}, Target Polygon Address: {target_polygon_address}")
    # This function will be expanded in Step 5: wCAS Minting Service
    # For now, it's a placeholder.
    # The actual implementation would likely involve an internal API call to the backend,
    # which then securely calls the smart contract.
    # Example:
    # mint_payload = {
    #     "cas_deposit_id": deposit_id, # To link the mint operation
    #     "amount_to_mint": amount,
    #     "recipient_polygon_address": target_polygon_address,
    #     "cas_deposit_address": cas_deposit_address # For logging/verification
    # }
    # try:
    #     response = requests.post(f"{BRIDGE_API_URL}/internal/initiate_wcas_mint", json=mint_payload, timeout=15)
    #     response.raise_for_status()
    #     logger.info(f"Successfully initiated wCAS minting for CasDeposit ID {deposit_id}. Response: {response.json()}")
    #     return True
    # except requests.exceptions.RequestException as e:
    #     logger.error(f"Failed to initiate wCAS minting for CasDeposit ID {deposit_id}: {e}")
    #     return False
    logger.info(f"[SIMULATION] Minting trigger successful for deposit ID {deposit_id}")
    return True # Simulate success for now

# --- Watcher Logic ---
def get_pending_deposit_addresses(db: DbSession):
    return db.query(CasDeposit).filter(CasDeposit.status == "pending").all()

def process_confirmed_deposit(db: DbSession, deposit_record: CasDeposit, amount_received: float):
    logger.info(f"Processing confirmed deposit for {deposit_record.cascoin_deposit_address} (ID: {deposit_record.id}), amount: {amount_received}")
    deposit_record.received_amount = amount_received
    deposit_record.status = "confirmed_cas" # Status: deposit confirmed on Cascoin
    deposit_record.updated_at = func.now()
    # db.commit() # Commit will be handled by the calling function after mint trigger

    if trigger_wcas_minting(deposit_record.id, amount_received, deposit_record.polygon_address, deposit_record.cascoin_deposit_address):
        deposit_record.status = "mint_triggered" # Status: minting process successfully triggered
        logger.info(f"CasDeposit ID {deposit_record.id} status updated to 'mint_triggered'.")
    else:
        deposit_record.status = "mint_trigger_failed" # Status: problem calling the mint service
        logger.error(f"Failed to trigger minting for CasDeposit ID {deposit_record.id}. Status set to 'mint_trigger_failed'.")
    db.commit()


def check_cascoin_transactions():
    db = SessionLocal()
    try:
        logger.info("Checking for new Cascoin deposits...")
        pending_deposits = get_pending_deposit_addresses(db)
        if not pending_deposits:
            logger.info("No pending Cascoin deposits to check.")
            return

        address_to_deposit_map = {dep.cascoin_deposit_address: dep for dep in pending_deposits}
        logger.info(f"Monitoring {len(address_to_deposit_map)} Cascoin addresses: {list(address_to_deposit_map.keys())}")

        current_block_height_response = cascoin_rpc_call("getblockcount")
        if not current_block_height_response or 'result' not in current_block_height_response:
            logger.warning("Could not get current Cascoin block height.")
            return
        current_block_height = current_block_height_response['result']
        logger.info(f"Current Cascoin block height: {current_block_height}")

        # This is the core logic that needs to be robust for a Bitcoin-like chain.
        # Option 1: If addresses are imported into the node's wallet (recommended for UTXO chains)
        #   - Use `listunspent(minconf, maxconf, ["address1", ...])` or `listtransactions`
        # Option 2: Scan blocks (less efficient for many addresses if not indexed by node)
        #   - `getblockhash(height)` -> `getblock(hash, verbosity=2)` -> iterate `tx` -> iterate `vout`
        # Option 3: Use a block explorer API if available (adds external dependency)

        # Placeholder simulation:
        # For now, we'll just iterate and simulate finding one.
        # In a real implementation, you'd query the node for UTXOs or transactions related to these addresses.
        for address_str, deposit_record in address_to_deposit_map.items():
            logger.debug(f"Simulating check for address: {address_str}")
            # --- !!! CRITICAL PLACEHOLDER START !!! ---
            # This section needs to be replaced with actual Cascoin node interaction
            # to find transactions for `address_str` and check their confirmations.
            #
            # Example (Conceptual - RPC calls depend on Cascoin's specific API):
            #
            # unspent_txs_response = cascoin_rpc_call("listunspent", [CONFIRMATIONS_REQUIRED, 9999999, [address_str]])
            # if unspent_txs_response and unspent_txs_response.get('result'):
            #     for utxo in unspent_txs_response['result']:
            #         if utxo['address'] == address_str and utxo['confirmations'] >= CONFIRMATIONS_REQUIRED:
            #             amount = utxo['amount']
            #             txid = utxo['txid'] # Important for tracking
            #             logger.info(f"Found confirmed UTXO for {address_str}: Amount {amount}, TXID {txid}")
            #             # Ensure this UTXO hasn't been processed before (e.g. by checking against a list of processed txids)
            #             process_confirmed_deposit(db, deposit_record, amount)
            #             # Potentially break if only one deposit per address is expected, or aggregate amounts.
            #             break # Process one UTXO per address for now
            #
            # --- !!! CRITICAL PLACEHOLDER END !!! ---

            # Simulate finding a deposit for the first pending address for dev purposes
            if deposit_record.id % 2 == 1: # Simulate for odd IDs to see some action
                 # Simulate that this one gets a "find"
                simulated_amount_received = 0.5 # Example amount
                logger.info(f"SIMULATING: Found confirmed deposit of {simulated_amount_received} CAS for {address_str} (ID: {deposit_record.id})")
                process_confirmed_deposit(db, deposit_record, simulated_amount_received)
                # To prevent it from being picked up again in next cycle in this simulation:
                # deposit_record.status = "mint_triggered" # or whatever process_confirmed_deposit sets it to
                # db.commit() # commit this change
                break # Simulate only one find per run to make logs cleaner

        logger.info("Finished Cascoin checking cycle.")

    except Exception as e:
        logger.error(f"Error during Cascoin checking cycle: {e}", exc_info=True)
        if db.is_active:
            db.rollback()
    finally:
        if db.is_active:
            db.close()

def main_loop():
    logger.info("Cascoin Watcher started.")
    logger.info(f"Cascoin RPC URL: {CASCOIN_RPC_URL}, Bridge API URL: {BRIDGE_API_URL}, DB: {DATABASE_URL}")
    logger.info(f"Polling every {POLL_INTERVAL_SECONDS}s, Confirmations Required: {CONFIRMATIONS_REQUIRED}")

    # Test Cascoin RPC connection on startup
    logger.info("Attempting initial connection to Cascoin node...")
    info = cascoin_rpc_call("getblockchaininfo")
    if info and info.get('result'):
        logger.info(f"Successfully connected to Cascoin node. Chain: {info['result'].get('chain')}, Blocks: {info['result'].get('blocks')}")
    else:
        logger.error("Failed to connect or get info from Cascoin node during startup. Please check RPC settings and node status. Watcher will continue trying.")

    while True:
        try:
            check_cascoin_transactions()
        except Exception as e:
            logger.error(f"Unhandled error in main loop: {e}", exc_info=True)

        logger.info(f"Sleeping for {POLL_INTERVAL_SECONDS} seconds...")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    # The watcher assumes the database and tables are already created by the backend.
    # If running standalone for testing, ensure bridge.db exists and tables are created.
    # from database.models import create_db_tables # If you had this in a shared models location
    # create_db_tables()
    main_loop()
