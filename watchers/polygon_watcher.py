import time
import json
import requests # For making HTTP requests to backend
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware # For PoA chains
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData
from sqlalchemy.orm import sessionmaker, Session as DbSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import logging
import os

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# IMPORTANT: Review and set these via environment variables for production.
# These should ideally be consistent with backend.config.settings or loaded from a shared config/env
POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https_rpc_mumbai_maticvigil_com") # From backend config
WCAS_CONTRACT_ADDRESS = os.getenv("WCAS_CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000") # From backend config, placeholder
WCAS_CONTRACT_ABI_JSON_PATH = os.getenv("WCAS_CONTRACT_ABI_JSON_PATH", "smart_contracts/wCAS_ABI.json") # From backend config
# Address on Polygon where users send their wCAS to be bridged back to Cascoin. This is monitored by the watcher.
BRIDGE_WCAS_COLLECTION_ADDRESS = os.getenv("BRIDGE_WCAS_DEPOSIT_ADDRESS", "0xYourBridgeWCASDepositAddressHereChangeMe") # From backend config

# Database URL - should match the backend's configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bridge.db")

# How often to check for new events/blocks on Polygon (in seconds)
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))

# Number of block confirmations on Polygon before a wCAS deposit is considered final
POLYGON_CONFIRMATIONS_REQUIRED = int(os.getenv("POLYGON_CONFIRMATIONS_REQUIRED", "12"))

# URL for the backend's internal API endpoints (for triggering CAS release)
# For Docker: use bridge-app:8000, for local dev: use localhost:8000
BRIDGE_API_URL = os.getenv("BRIDGE_API_URL", "http://bridge-app:8000/internal")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "bridge_internal_secret_key_change_me_!!!")

# Post-process RPC URL (e.g. Infura often provides https_rpc... format)
if POLYGON_RPC_URL.startswith("https_"):
    POLYGON_RPC_URL = POLYGON_RPC_URL.replace("https_", "https://", 1)

# --- Database Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Mirrored PolygonTransaction model from database.models
class PolygonTransaction(Base):
    __tablename__ = "polygon_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_cascoin_address_request = Column(String, index=True, nullable=False) # User's desired CAS address
    from_address = Column(String, index=True, nullable=False) # User's Polygon address that sent wCAS
    to_address = Column(String, index=True, nullable=False) # Should be BRIDGE_WCAS_COLLECTION_ADDRESS
    amount = Column(Float, nullable=False) # Amount of wCAS received
    polygon_tx_hash = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="pending_confirmation", index=True) # e.g., pending_confirmation, confirmed_wcas, processing_cas_release, cas_released, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    cas_release_tx_hash = Column(String, nullable=True)

    def __repr__(self):
        return f"<PolygonTransaction(id={self.id}, poly_tx='{self.polygon_tx_hash}', status='{self.status}')>"

# Mirrored WcasToCasReturnIntention model from database.models
class WcasToCasReturnIntention(Base):
    __tablename__ = "wcas_to_cas_return_intentions"
    id = Column(Integer, primary_key=True, index=True)
    user_polygon_address = Column(String, index=True, nullable=False)
    target_cascoin_address = Column(String, nullable=False)
    status = Column(String, default="pending_deposit", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<WcasToCasReturnIntention(id={self.id}, poly_addr='{self.user_polygon_address}', cas_addr='{self.target_cascoin_address}', status='{self.status}')>"

# --- Web3 Setup ---
w3 = None
wcas_contract = None
wcas_decimals = 18 # Default, will try to load from contract

def load_wcas_abi():
    global WCAS_CONTRACT_ABI_JSON_PATH # Allow modification for path testing
    abi = []
    # Try to resolve path relative to the project root
    project_root_abi_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), WCAS_CONTRACT_ABI_JSON_PATH)

    if os.path.exists(WCAS_CONTRACT_ABI_JSON_PATH):
        pass
    elif os.path.exists(project_root_abi_path):
        WCAS_CONTRACT_ABI_JSON_PATH = project_root_abi_path

    if os.path.exists(WCAS_CONTRACT_ABI_JSON_PATH):
        try:
            with open(WCAS_CONTRACT_ABI_JSON_PATH, 'r') as f:
                abi = json.load(f)
            logger.info(f"Successfully loaded wCAS ABI from {WCAS_CONTRACT_ABI_JSON_PATH}")
        except Exception as e:
            logger.error(f"Error loading ABI from {WCAS_CONTRACT_ABI_JSON_PATH}: {e}", exc_info=True)
    else:
        logger.error(f"ABI file not found: {WCAS_CONTRACT_ABI_JSON_PATH} or {project_root_abi_path}")
    return abi

def setup_web3_and_contract():
    global w3, wcas_contract, wcas_decimals
    logger.info(f"Connecting to Polygon node at {POLYGON_RPC_URL}...")
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL, request_kwargs={'timeout': 60}))

    if "mumbai" in POLYGON_RPC_URL.lower() or "matic" in POLYGON_RPC_URL.lower() or "polygon" in POLYGON_RPC_URL.lower():
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        logger.info("Injected PoA middleware for Polygon.")

    if not w3.is_connected():
        logger.error("Failed to connect to Polygon node.")
        return False # Indicate failure

    logger.info(f"Connected to Polygon. Chain ID: {w3.eth.chain_id}")

    wcas_abi = load_wcas_abi()
    if not wcas_abi:
        logger.error("wCAS ABI not loaded. Cannot initialize contract.")
        return False

    if not WCAS_CONTRACT_ADDRESS or WCAS_CONTRACT_ADDRESS == "0x0000000000000000000000000000000000000000":
        logger.error("WCAS_CONTRACT_ADDRESS is not configured or is a placeholder.")
        return False

    try:
        wcas_contract = w3.eth.contract(address=Web3.to_checksum_address(WCAS_CONTRACT_ADDRESS), abi=wcas_abi)
        wcas_decimals = wcas_contract.functions.decimals().call() # Get decimals from contract
        logger.info(f"wCAS contract loaded. Address: {WCAS_CONTRACT_ADDRESS}, Decimals: {wcas_decimals}")
    except Exception as e:
        logger.error(f"Error loading wCAS contract or getting decimals: {e}", exc_info=True)
        logger.warning("Falling back to 18 decimals if contract interaction failed.")
        wcas_decimals = 18 # Fallback
        # If contract object itself failed to init, wcas_contract will be None
        if not wcas_contract: return False

    return True


# --- Backend API Interaction (Placeholder for CAS Release Trigger) ---
def trigger_cas_release(polygon_tx_record_id: int, amount_wcas: float, target_cas_address: str):
    logger.info(f"Attempting to trigger CAS release for PolygonTransaction ID: {polygon_tx_record_id}, Amount: {amount_wcas} wCAS to {target_cas_address}")

    release_payload = {
        "polygon_transaction_id": polygon_tx_record_id,
        "amount_to_release": amount_wcas, # Assuming 1 wCAS = 1 CAS
        "recipient_cascoin_address": target_cas_address
    }

    headers = {'Content-Type': 'application/json', 'X-Internal-API-Key': INTERNAL_API_KEY}
    api_endpoint = f"{BRIDGE_API_URL}/initiate_cas_release"

    try:
        response = requests.post(api_endpoint, json=release_payload, headers=headers, timeout=15)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        logger.info(f"Successfully initiated CAS release for Polygon Tx ID {polygon_tx_record_id}. Backend response: {response.json()}")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Timeout calling backend API to initiate CAS release for Polygon Tx ID {polygon_tx_record_id} at {api_endpoint}")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error calling backend API to initiate CAS release for Polygon Tx ID {polygon_tx_record_id} at {api_endpoint}")
        return False
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from backend API for Polygon Tx ID {polygon_tx_record_id}: {e}. Response: {e.response.text if e.response else 'No response text'}")
        return False
    except Exception as e: # Catch any other exceptions
        logger.error(f"Generic error calling backend API for Polygon Tx ID {polygon_tx_record_id}: {e}", exc_info=True)
        return False

# --- Polygon Watcher Logic ---
def get_last_processed_block(db: DbSession) -> int:
    # For simplicity, store last processed block in a file or small DB table.
    # Here, we'll use a file. In a robust app, use a dedicated DB table.
    try:
        with open("polygon_last_block.txt", "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        logger.info("polygon_last_block.txt not found, will fetch current block number as starting point.")
        # Fetch a recent block to avoid scanning the entire chain history on first run
        # Be careful not to miss events if the watcher was down for a long time.
        # A safer start would be current_block - N, where N is a small number.
        try:
            return w3.eth.block_number - 10 # Start 10 blocks behind to be safe
        except Exception as e:
            logger.error(f"Could not fetch current block number to initialize, defaulting to 0: {e}")
            return 0 # Fallback, will scan from genesis if node allows or very recent history.
    except ValueError:
        logger.error("Invalid content in polygon_last_block.txt, starting from 0.")
        return 0


def save_last_processed_block(db: DbSession, block_number: int):
    with open("polygon_last_block.txt", "w") as f:
        f.write(str(block_number))

def check_polygon_events():
    global w3, wcas_contract, wcas_decimals
    if not w3 or not wcas_contract:
        logger.error("Web3 or wCAS contract not initialized. Skipping check.")
        if not setup_web3_and_contract(): # Try to re-initialize
            return # If still fails, skip this cycle

    db = SessionLocal()
    try:
        from_block = get_last_processed_block(db) + 1
        # Ensure BRIDGE_WCAS_COLLECTION_ADDRESS is checksummed
        checksum_bridge_address = Web3.to_checksum_address(BRIDGE_WCAS_COLLECTION_ADDRESS)

        to_block = w3.eth.block_number
        if from_block > to_block:
            logger.info(f"No new blocks to process. From: {from_block}, To: {to_block}")
            return

        logger.info(f"Scanning for wCAS 'Transfer' events to {checksum_bridge_address} from block {from_block} to {to_block}...")

        # Query Transfer events where 'to' is our bridge's collection address using get_logs
        # This avoids the need for eth_newFilter which many RPC providers disable
        transfer_event_signature = wcas_contract.events.Transfer.build_filter()
        transfer_topic = transfer_event_signature.topics[0]
        
        # Create filter parameters for get_logs
        filter_params = {
            'fromBlock': hex(from_block),
            'toBlock': hex(to_block),
            'address': wcas_contract.address,
            'topics': [
                transfer_topic,  # Transfer event signature
                None,            # from address (any)
                Web3.to_hex(int(checksum_bridge_address, 16).to_bytes(32, byteorder='big'))  # to address (our bridge)
            ]
        }
        
        # Get logs directly from the node
        logs = w3.eth.get_logs(filter_params)
        
        # Process logs into event objects
        new_events = []
        for log in logs:
            try:
                event = wcas_contract.events.Transfer().process_log(log)
                new_events.append(event)
            except Exception as e:
                logger.warning(f"Could not process log {log['transactionHash'].hex()}: {e}")
                continue

        if new_events:
            logger.info(f"Found {len(new_events)} new wCAS Transfer event(s) to the bridge address.")
            for event in new_events:
                tx_hash = event['transactionHash'].hex()
                log_index = event['logIndex']
                block_number = event['blockNumber']

                # Check if this event (by tx_hash and log_index) has already been processed
                existing_tx = db.query(PolygonTransaction).filter_by(polygon_tx_hash=tx_hash, from_address=event.args['from']).first() # More specific check
                if existing_tx:
                    logger.info(f"Event for tx {tx_hash} (logIndex {log_index}) already processed or pending. Status: {existing_tx.status}. Skipping.")
                    continue

                logger.info(f"Processing event: TxHash: {tx_hash}, From: {event.args['from']}, To: {event.args['to']}, Value: {event.args['value']}")

                # 1. Store the transaction with 'pending_polygon_confirmation'
                amount_float = float(event.args['value']) / (10**wcas_decimals)

                # The user's Cascoin address is not in the event.
                # The frontend (Step 8) for Polygon -> Cascoin should have collected this.
                # For now, we'll use a placeholder. This needs to be linked to the actual user request.
                # This is a CRITICAL GAP to be filled by frontend/backend interaction.
                # A common pattern: user calls an API endpoint like /initiatePolyToCas (providing their CAS address),
                # backend gives them a unique ID or expects them to send wCAS with a specific memo/data field if possible.
                # Or, the user's Polygon address (event.args['from']) is linked to their Cascoin address in our DB.

                # For this watcher, let's assume the backend has a way to map event.args['from'] (user's Polygon addr)
                # Checksum the address from the event for consistent DB lookups
                user_polygon_address_checksum = Web3.to_checksum_address(event.args['from'])
                amount_float = float(event.args['value']) / (10**wcas_decimals)

                target_cas_address = "UNKNOWN_NO_INTENTION" # Default if no intention found
                poly_tx_status = "on_hold_no_intention"     # Default status

                # Fetch the user's intention from the database
                intention = db.query(WcasToCasReturnIntention)\
                    .filter(WcasToCasReturnIntention.user_polygon_address == user_polygon_address_checksum)\
                    .filter(WcasToCasReturnIntention.status == "pending_deposit")\
                    .order_by(WcasToCasReturnIntention.created_at.desc())\
                    .first()

                if intention:
                    logger.info(f"Found pending intention for {user_polygon_address_checksum}: ID {intention.id}, Target CAS: {intention.target_cascoin_address}")
                    target_cas_address = intention.target_cascoin_address
                    poly_tx_status = "pending_polygon_confirmation" # Ready for confirmation

                    # Update intention status to 'deposit_detected'
                    intention.status = "deposit_detected"
                    intention.updated_at = func.now()
                    # The commit for this will happen with the PolygonTransaction record
                else:
                    logger.warning(f"No 'pending_deposit' intention found for wCAS sender: {user_polygon_address_checksum}. Holding transaction.")

                new_poly_tx = PolygonTransaction(
                    user_cascoin_address_request=target_cas_address,
                    from_address=user_polygon_address_checksum, # Use checksummed address
                    to_address=Web3.to_checksum_address(event.args['to']), # Also checksum bridge address
                    amount=amount_float,
                    polygon_tx_hash=tx_hash,
                    status=poly_tx_status
                )
                db.add(new_poly_tx)
                db.commit() # Commit both new_poly_tx and updated intention (if any)
                db.refresh(new_poly_tx)
                if intention: # Refresh intention if it was updated
                    db.refresh(intention)
                logger.info(f"Stored new PolygonTransaction ID {new_poly_tx.id} for tx {tx_hash} with status '{poly_tx_status}'. Target CAS Address: {target_cas_address}")
        else:
            logger.info("No new relevant wCAS Transfer events found.")

        # Check confirmations for transactions in 'pending_polygon_confirmation'
        # This part of the logic remains largely the same but will only effectively proceed for transactions
        # that were created with status 'pending_polygon_confirmation' (i.e., an intention was found).
        pending_confirmation_txs = db.query(PolygonTransaction).filter(PolygonTransaction.status == "pending_polygon_confirmation").all()
        if pending_confirmation_txs:
            logger.info(f"Checking confirmations for {len(pending_confirmation_txs)} Polygon transactions...")
            current_polygon_block = w3.eth.block_number
            for tx_record in pending_confirmation_txs:
                try:
                    tx_receipt = w3.eth.get_transaction_receipt(tx_record.polygon_tx_hash)
                    if tx_receipt:
                        tx_block_number = tx_receipt.blockNumber
                        confirmations = current_polygon_block - tx_block_number
                        logger.info(f"Tx {tx_record.polygon_tx_hash}: Block {tx_block_number}, Current Block {current_polygon_block}, Confirmations: {confirmations}")

                        if confirmations >= POLYGON_CONFIRMATIONS_REQUIRED:
                            logger.info(f"Tx {tx_record.polygon_tx_hash} (ID: {tx_record.id}) has {confirmations} confirmations. Sufficiently confirmed.")
                            tx_record.status = "wcas_confirmed"
                            tx_record.updated_at = func.now()
                            # db.commit() # Commit will be done after triggering release attempt

                            if tx_record.user_cascoin_address_request == "UNKNOWN_NO_INTENTION":
                                logger.error(f"Tx {tx_record.polygon_tx_hash} (ID: {tx_record.id}) confirmed but has no target Cascoin address. Status remains 'wcas_confirmed', requires manual intervention.")
                                # No CAS release trigger if address is unknown
                            elif trigger_cas_release(tx_record.id, tx_record.amount, tx_record.user_cascoin_address_request):
                                tx_record.status = "cas_release_triggered"
                                logger.info(f"PolygonTransaction ID {tx_record.id} status updated to 'cas_release_triggered'.")
                            else:
                                tx_record.status = "cas_release_trigger_failed"
                                logger.error(f"Failed to trigger CAS release for PolygonTransaction ID {tx_record.id}.")
                            db.commit() # Commit status changes for tx_record
                        else:
                            logger.info(f"Tx {tx_record.polygon_tx_hash} (ID: {tx_record.id}) has {confirmations}/{POLYGON_CONFIRMATIONS_REQUIRED} confirmations. Waiting.")
                    else:
                        logger.warning(f"Could not get receipt for tx {tx_record.polygon_tx_hash} (ID: {tx_record.id}). It might not be mined yet or is invalid.")
                except Exception as e:
                    logger.error(f"Error checking confirmations for tx {tx_record.polygon_tx_hash} (ID: {tx_record.id}): {e}", exc_info=True)
                    db.rollback() # Rollback any single tx confirmation error

        save_last_processed_block(db, to_block)

    except Exception as e:
        logger.error(f"Error during Polygon event checking cycle: {e}", exc_info=True)
        if db.is_active:
            db.rollback()
    finally:
        if db.is_active:
            db.close()


def main_loop():
    logger.info("Polygon Watcher started.")
    if not setup_web3_and_contract():
        logger.error("Initial Web3/Contract setup failed. Polygon Watcher may not function correctly. Will retry periodically.")

    logger.info(f"Watching for wCAS transfers to: {BRIDGE_WCAS_COLLECTION_ADDRESS} on contract {WCAS_CONTRACT_ADDRESS}")
    logger.info(f"Polling every {POLL_INTERVAL_SECONDS}s, Polygon Confirmations Required: {POLYGON_CONFIRMATIONS_REQUIRED}")

    while True:
        try:
            check_polygon_events()
        except Exception as e:
            logger.error(f"Unhandled error in main Polygon watcher loop: {e}", exc_info=True)
            # Consider a backoff or attempt to re-initialize Web3 connection if it fails repeatedly
            if "connection" in str(e).lower() or "node" in str(e).lower():
                logger.info("Attempting to re-initialize Web3 connection and contract due to error...")
                time.sleep(POLL_INTERVAL_SECONDS) # Wait before retrying connection
                setup_web3_and_contract()

        logger.info(f"Polygon watcher sleeping for {POLL_INTERVAL_SECONDS} seconds...")
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    # Ensure DB tables exist - Critical for polygon watcher to work
    try:
        Base.metadata.create_all(engine)
        logger.info("Database tables created or verified to exist.")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}", exc_info=True)
        raise SystemExit(1)
    # Ensure DB tables exist (usually backend's job)
    # Base.metadata.create_all(engine) # If watcher runs fully standalone with its own model defs
    main_loop()
