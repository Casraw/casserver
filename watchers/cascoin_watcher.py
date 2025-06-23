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
# For Docker: use bridge-app:8000, for local dev: use localhost:8000
BRIDGE_API_URL = os.getenv("BRIDGE_API_URL", "http://bridge-app:8000/internal")
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
    # Added fields for confirmation tracking
    current_confirmations = Column(Integer, default=0)
    required_confirmations = Column(Integer, default=12)
    deposit_tx_hash = Column(String, nullable=True)  # Track the transaction hash
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
def _send_deposit_update_notification(deposit_id: int):
    """Helper to send a websocket notification for a deposit update."""
    try:
        headers = {'Content-Type': 'application/json', 'X-Internal-API-Key': INTERNAL_API_KEY}
        notify_payload = {"deposit_id": deposit_id}
        requests.post(f"{BRIDGE_API_URL}/notify_deposit_update", json=notify_payload, headers=headers, timeout=5)
        logger.info(f"Sent websocket notification for deposit {deposit_id}.")
    except Exception as e:
        logger.warning(f"Failed to send websocket notification for deposit {deposit_id}: {e}")

def check_confirmation_updates():
    """
    Check deposits that are in 'pending_confirmation' status and update their confirmation count
    """
    db: DbSession = SessionLocal()
    try:
        logger.info("Checking confirmation updates for 'pending_confirmation' deposits...")

        pending_deposit_ids = [d.id for d in db.query(CasDeposit.id).filter(CasDeposit.status == "pending_confirmation").all()]

        if not pending_deposit_ids:
            logger.info("No deposits are currently 'pending_confirmation'.")
            return

        logger.info(f"Found {len(pending_deposit_ids)} deposit(s) to check for confirmation updates.")

        for deposit_id in pending_deposit_ids:
            # Process each deposit in its own transaction context
            session: DbSession = SessionLocal()
            try:
                deposit_record = session.query(CasDeposit).filter_by(id=deposit_id).first()
                if not deposit_record:
                    logger.warning(f"Deposit ID {deposit_id} not found, might have been processed or deleted.")
                    continue
                
                if not deposit_record.deposit_tx_hash:
                    logger.warning(f"Deposit ID {deposit_record.id} is 'pending_confirmation' but has no transaction hash. Skipping.")
                    continue

                # Get transaction details
                tx_response = cascoin_rpc_call("gettransaction", [deposit_record.deposit_tx_hash])
                
                if tx_response is None or tx_response.get("error"):
                    logger.warning(f"Could not get transaction details for {deposit_record.deposit_tx_hash} (Deposit ID: {deposit_record.id}). Will retry next cycle.")
                    continue

                tx_data = tx_response.get("result", {})
                new_confirmations = tx_data.get("confirmations", 0)
                old_confirmations = deposit_record.current_confirmations

                # If already fully confirmed but status wasn't updated yet, proceed
                if new_confirmations >= CONFIRMATIONS_REQUIRED and deposit_record.status != "cas_confirmed_pending_mint":
                    logger.info(
                        f"Deposit ID {deposit_record.id}: Reached required confirmations (" \
                        f"{new_confirmations}/{CONFIRMATIONS_REQUIRED}) while status is still '{deposit_record.status}'."
                    )
                    # fall through to processing block below
                elif new_confirmations == old_confirmations:
                    # No change and not yet fully confirmed – skip to next deposit
                    logger.info(
                        f"Deposit ID {deposit_record.id}: Confirmations unchanged at {new_confirmations}. No update needed."
                    )
                    continue
                
                # --- Confirmation count has changed, process update ---
                logger.info(f"Deposit ID {deposit_record.id}: Confirmation count changed from {old_confirmations} to {new_confirmations}.")

                deposit_record.current_confirmations = new_confirmations
                deposit_record.required_confirmations = CONFIRMATIONS_REQUIRED
                
                # Check if fully confirmed
                if new_confirmations >= CONFIRMATIONS_REQUIRED:
                    deposit_record.status = "cas_confirmed_pending_mint"
                    logger.info(f"Deposit ID {deposit_record.id} is now fully confirmed with {new_confirmations} confirmations. Status set to 'cas_confirmed_pending_mint'.")
                    
                    if deposit_record.received_amount is None:
                        for detail in tx_data.get("details", []):
                            if detail.get("address") == deposit_record.cascoin_deposit_address and detail.get("category") == "receive":
                                deposit_record.received_amount = abs(detail.get("amount", 0))
                                break
                    
                    deposit_record.updated_at = func.now()
                    session.commit()
                    _send_deposit_update_notification(deposit_record.id)

                    # Check if this deposit has a gas deposit requirement (BYO-gas flow)
                    # Import here to avoid circular imports
                    from backend.crud import get_polygon_gas_deposit_by_cas_deposit_id
                    gas_deposit = get_polygon_gas_deposit_by_cas_deposit_id(session, deposit_record.id)
                    
                    if gas_deposit:
                        if gas_deposit.status == "funded":
                            logger.info(f"Deposit ID {deposit_record.id}: Gas deposit is funded, proceeding with minting")
                            should_trigger_mint = True
                        else:
                            logger.info(f"Deposit ID {deposit_record.id}: Waiting for gas deposit funding (status: {gas_deposit.status})")
                            should_trigger_mint = False
                    else:
                        logger.info(f"Deposit ID {deposit_record.id}: No gas deposit found, using traditional flow")
                        should_trigger_mint = True

                    if deposit_record.received_amount and deposit_record.received_amount > 0:
                        if should_trigger_mint:
                            mint_triggered = trigger_wcas_minting(
                                deposit_id=deposit_record.id,
                                amount_to_mint=deposit_record.received_amount,
                                recipient_polygon_address=deposit_record.polygon_address,
                                cas_deposit_address=deposit_record.cascoin_deposit_address
                            )
                            
                            if mint_triggered:
                                deposit_record.status = "mint_triggered"
                                logger.info(f"wCAS minting triggered for deposit ID {deposit_record.id}")
                            else:
                                deposit_record.status = "mint_trigger_failed"
                                logger.error(f"Failed to trigger minting for deposit ID {deposit_record.id}")
                        else:
                            deposit_record.status = "cas_confirmed_awaiting_gas"
                            logger.info(f"Deposit ID {deposit_record.id}: CAS confirmed, waiting for gas funding")
                        
                        deposit_record.updated_at = func.now()
                        session.commit()
                        _send_deposit_update_notification(deposit_record.id)
                        logger.info(f"Deposit ID {deposit_record.id}: Committed final status '{deposit_record.status}'.")

                else:
                    deposit_record.updated_at = func.now()
                    session.commit()
                    _send_deposit_update_notification(deposit_record.id)
                    logger.info(f"Deposit ID {deposit_record.id}: Committed updated confirmation count '{deposit_record.current_confirmations}'.")
                
            except Exception as e:
                logger.error(f"An error occurred while checking confirmations for deposit {deposit_id}: {e}", exc_info=True)
                if session.is_active:
                    session.rollback()
            finally:
                if session.is_active:
                    session.close()

    except Exception as e:
        logger.error(f"Error in confirmation checking cycle: {e}", exc_info=True)
    finally:
        if db.is_active:
            db.close()

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

            # Find any unspent transaction for the address. We start with 0 confirmations.
            # This will find any new transaction, regardless of its current confirmation count.
            listunspent_params = [0, 9999999, [address_str], False]
            rpc_response = cascoin_rpc_call("listunspent", listunspent_params)

            if rpc_response is None:
                logger.warning(f"RPC call 'listunspent' failed for address {address_str}. Skipping this address for now.")
                continue
            
            if rpc_response.get("error") is not None:
                logger.error(f"RPC error for listunspent on address {address_str}: {rpc_response['error']}")
                continue

            unspent_txs = rpc_response.get("result", [])
            if not unspent_txs:
                logger.info(f"No transactions found for address {address_str}.")
                continue

            # Process the first unprocessed UTXO we find for this deposit address.
            # This assumes a 1-to-1 relationship between a deposit address and a deposit event.
            for utxo in unspent_txs:
                txid = utxo.get('txid')
                vout_index = utxo.get('vout')

                # Verify this UTXO hasn't been used for another deposit.
                # This check is crucial to prevent re-processing the same on-chain transaction.
                is_processed = db.query(ProcessedCascoinTxs).filter_by(cascoin_txid=txid, cascoin_vout_index=vout_index).first()
                if is_processed:
                    logger.info(f"UTXO {txid}-{vout_index} has already been processed for deposit {is_processed.cas_deposit_id}. Skipping.")
                    continue

                # Found a new transaction. Associate it with this deposit record.
                confirmations = utxo.get('confirmations', 0)
                amount_received_cas = utxo.get('amount')
                
                logger.info(f"Detected new transaction {txid} for deposit {deposit_record.id} with {confirmations} confirmations.")

                deposit_record.deposit_tx_hash = txid
                deposit_record.received_amount = amount_received_cas
                deposit_record.current_confirmations = confirmations
                deposit_record.required_confirmations = CONFIRMATIONS_REQUIRED
                deposit_record.status = "pending_confirmation"  # Hand over to check_confirmation_updates
                deposit_record.updated_at = func.now()

                db.commit()

                # Send a websocket notification that we've detected the transaction.
                try:
                    headers = {'Content-Type': 'application/json', 'X-Internal-API-Key': INTERNAL_API_KEY}
                    notify_payload = {"deposit_id": deposit_record.id}
                    requests.post(f"{BRIDGE_API_URL}/notify_deposit_update", json=notify_payload, headers=headers, timeout=5)
                    logger.info(f"Sent initial detection notification for deposit {deposit_record.id}.")
                except Exception as e:
                    logger.warning(f"Failed to send initial websocket notification for deposit {deposit_record.id}: {e}")
                
                # Once we've associated a transaction with this deposit, move to the next deposit.
                break  # Exit the 'for utxo in unspent_txs' loop
            
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
            check_confirmation_updates()
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
