import time
import json
import requests # For making HTTP requests to backend and Cascoin RPC
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, ForeignKey, UniqueConstraint
from sqlalchemy.orm import sessionmaker, Session as DbSession # Renamed to avoid conflict
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import logging
import os # Added for environment variable access

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# IMPORTANT: Review and set these via environment variables for production.
CASCOIN_RPC_URL = os.getenv("CASCOIN_RPC_URL", "http://localhost:18332")
CASCOIN_RPC_USER = os.getenv("CASCOIN_RPC_USER", "your_cascoin_rpc_user")
CASCOIN_RPC_PASSWORD = os.getenv("CASCOIN_RPC_PASSWORD", "your_cascoin_rpc_password") # Sensitive: Set in ENV

# URL for the backend's internal API endpoints
BRIDGE_API_URL = os.getenv("BRIDGE_API_URL", "http://localhost:8000/internal")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "bridge_internal_secret_key_change_me_!!!")

# Database URL - should match the backend's configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bridge.db")

# How often to poll the Cascoin node for new transactions (in seconds)
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

# Number of confirmations on Cascoin blockchain before a deposit is considered final
CONFIRMATIONS_REQUIRED = int(os.getenv("CONFIRMATIONS_REQUIRED", "6"))

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

# Definition for ProcessedCascoinTxs table (mirrored from database.models)
class ProcessedCascoinTxs(Base):
    __tablename__ = "processed_cascoin_txs"

    id = Column(Integer, primary_key=True, index=True)
    cascoin_txid = Column(String, index=True, nullable=False)
    cascoin_vout_index = Column(Integer, nullable=False)
    cas_deposit_id = Column(Integer, ForeignKey("cas_deposits.id"), nullable=False)
    amount_received = Column(Float, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('cascoin_txid', 'cascoin_vout_index', name='_cascoin_txid_vout_uc'),)

    def __repr__(self):
        return f"<ProcessedCascoinTxs(id={self.id}, txid='{self.cascoin_txid}', vout_index={self.cascoin_vout_index})>"

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

# --- Backend API Interaction ---
def trigger_wcas_minting(deposit_id: int, amount_to_mint: float, recipient_polygon_address: str, cas_deposit_address: str):
    """
    Triggers the wCAS minting process by calling the backend's internal API.
    """
    logger.info(f"Attempting to trigger wCAS minting for CasDeposit ID: {deposit_id}, Amount: {amount_to_mint}, Target Polygon Address: {recipient_polygon_address}")

    mint_payload = {
        "cas_deposit_id": deposit_id,
        "amount_to_mint": amount_to_mint,
        "recipient_polygon_address": recipient_polygon_address,
        "cas_deposit_address": cas_deposit_address # For logging/verification by backend
    }

    # Ensure BRIDGE_API_URL points to the internal API, e.g., http://localhost:8000/internal
    api_endpoint = f"{BRIDGE_API_URL}/initiate_wcas_mint"

    try:
        headers = {'Content-Type': 'application/json', 'X-Internal-API-Key': INTERNAL_API_KEY}
        response = requests.post(api_endpoint, json=mint_payload, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        logger.info(f"Successfully initiated wCAS minting for CasDeposit ID {deposit_id}. Backend response: {response.json()}")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Timeout calling backend API to initiate minting for CasDeposit ID {deposit_id} at {api_endpoint}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error calling backend API to initiate minting for CasDeposit ID {deposit_id} at {api_endpoint}")
        return False
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from backend API for CasDeposit ID {deposit_id}: {e}. Response: {e.response.text if e.response else 'No response text'}")
        return False
    except Exception as e:
        logger.error(f"Generic error calling backend API for CasDeposit ID {deposit_id}: {e}", exc_info=True)
        return False

# --- Watcher Logic ---
def check_cascoin_transactions():
    db: DbSession = SessionLocal()
    try:
        logger.info("Checking for new Cascoin deposits...")

        # Get CasDeposit records with "pending" status
        pending_deposits = db.query(CasDeposit).filter(CasDeposit.status == "pending").all()

        if not pending_deposits:
            logger.info("No pending Cascoin deposits to check.")
            return

        logger.info(f"Found {len(pending_deposits)} pending deposit(s). Checking their Cascoin addresses...")

        for deposit_record in pending_deposits:
            address_str = deposit_record.cascoin_deposit_address
            logger.info(f"Checking address: {address_str} for CasDeposit ID: {deposit_record.id}")

            # Call listunspent for the specific address
            # Parameters: [minconf, maxconf, ["address",...], include_unsafe, query_options]
            # We want confirmed UTXOs, so include_unsafe = False
            # query_options can be omitted or set to default if not needed.
            # Note: some nodes might have slightly different param order or requirements for listunspent.
            # This assumes a common Bitcoin Core-like API.
            listunspent_params = [CONFIRMATIONS_REQUIRED, 9999999, [address_str], False]

            rpc_response = cascoin_rpc_call("listunspent", listunspent_params)

            if rpc_response is None: # Error logged by cascoin_rpc_call
                logger.warning(f"RPC call 'listunspent' failed for address {address_str}. Skipping this address for now.")
                continue

            # Check for RPC errors
            if rpc_response.get("error") is not None:
                logger.error(f"RPC error for listunspent on address {address_str}: {rpc_response['error']}")
                continue

            # Extract the result from the RPC response
            unspent_txs = rpc_response.get("result", [])

            if not isinstance(unspent_txs, list):
                logger.error(f"Unexpected format for listunspent result for address {address_str}. Expected list, got: {type(unspent_txs)}. Response: {rpc_response}")
                continue

            if not unspent_txs:
                logger.info(f"No confirmed UTXOs found for address {address_str} with {CONFIRMATIONS_REQUIRED} confirmations.")
                continue

            logger.info(f"Found {len(unspent_txs)} UTXO(s) for address {address_str} meeting {CONFIRMATIONS_REQUIRED} confirmations.")

            for utxo in unspent_txs:
                try:
                    txid = utxo.get('txid')
                    vout_index = utxo.get('vout')
                    amount_received_cas = utxo.get('amount') # Assuming 'amount' is in CAS
                    actual_confirmations = utxo.get('confirmations')

                    if not all([txid, isinstance(vout_index, int), isinstance(amount_received_cas, (float, int))]):
                        logger.warning(f"Skipping UTXO with incomplete data for address {address_str}: txid={txid}, vout={vout_index}, amount={amount_received_cas}")
                        continue

                    logger.info(f"Processing UTXO: TXID={txid}, Vout={vout_index}, Amount={amount_received_cas}, Confirmations={actual_confirmations} for Deposit ID {deposit_record.id}")

                    # Check if this UTXO has already been processed
                    existing_processed_tx = db.query(ProcessedCascoinTxs).filter_by(
                        cascoin_txid=txid,
                        cascoin_vout_index=vout_index
                    ).first()

                    if existing_processed_tx:
                        logger.info(f"UTXO {txid}-{vout_index} already processed for CasDeposit ID {existing_processed_tx.cas_deposit_id}. Skipping.")
                        continue

                    # Store this UTXO as processed
                    new_processed_tx = ProcessedCascoinTxs(
                        cascoin_txid=txid,
                        cascoin_vout_index=vout_index,
                        cas_deposit_id=deposit_record.id,
                        amount_received=amount_received_cas
                    )
                    db.add(new_processed_tx)

                    # Update CasDeposit record
                    # For now, assuming one UTXO per deposit triggers minting.
                    # If aggregation is needed, this logic would change: accumulate amounts,
                    # and only trigger minting when a threshold is met or after a certain time.
                    deposit_record.received_amount = amount_received_cas # Overwrites if multiple UTXOs are found, simple model for now
                    deposit_record.status = "cas_confirmed_pending_mint" # New status
                    deposit_record.updated_at = func.now()

                    logger.info(f"CasDeposit ID {deposit_record.id} updated: amount={amount_received_cas}, status='cas_confirmed_pending_mint'")

                    # Commit the status change BEFORE calling the API to prevent a race condition
                    db.commit()

                    # Trigger wCAS minting via backend API
                    mint_triggered = trigger_wcas_minting(
                        deposit_id=deposit_record.id,
                        amount_to_mint=amount_received_cas, # Assuming 1 CAS = 1 wCAS
                        recipient_polygon_address=deposit_record.polygon_address,
                        cas_deposit_address=deposit_record.cascoin_deposit_address
                    )

                    if mint_triggered:
                        deposit_record.status = "mint_triggered" # Or "mint_initiated"
                        logger.info(f"wCAS minting successfully triggered for CasDeposit ID {deposit_record.id}.")
                    else:
                        deposit_record.status = "mint_trigger_failed"
                        logger.error(f"Failed to trigger wCAS minting for CasDeposit ID {deposit_record.id}. Status set to 'mint_trigger_failed'.")

                    db.commit() # Commit the final status update (mint_triggered or mint_trigger_failed)
                    logger.info(f"Successfully processed and committed UTXO {txid}-{vout_index} for CasDeposit ID {deposit_record.id}.")

                except Exception as e_utxo:
                    logger.error(f"Error processing UTXO {utxo.get('txid')}-{utxo.get('vout')} for deposit {deposit_record.id}: {e_utxo}", exc_info=True)
                    db.rollback() # Rollback changes for this specific UTXO

        logger.info("Finished Cascoin checking cycle for pending deposits.")

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
    if info and info.get('error') is None and info.get('result'):
        logger.info(f"Successfully connected to Cascoin node. Chain: {info['result'].get('chain')}, Blocks: {info['result'].get('blocks')}")
    else:
        error_msg = info.get('error') if info else "No response"
        logger.error(f"Failed to connect or get info from Cascoin node during startup. Error: {error_msg}. Please check RPC settings and node status. Watcher will continue trying.")

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
