from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import logging # Added for logging

from backend import schemas, crud # schemas for request/response models, crud for DB ops
from backend.database import get_db # get_db for dependency injection
from backend.services.polygon_service import PolygonService
from backend.services.cascoin_service import CascoinService # Added CascoinService
from backend.config import settings # For INTERNAL_API_KEY

# Initialize logger for this module
logger = logging.getLogger(__name__)

router = APIRouter()

# --- Helper function for API Key Check ---
def verify_api_key(x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key")):
    # Ensure settings.INTERNAL_API_KEY has a value and is not the default placeholder if in prod.
    # For now, direct comparison.
    if not settings.INTERNAL_API_KEY or settings.INTERNAL_API_KEY == "bridge_internal_secret_key_change_me_!!!":
        logger.critical("INTERNAL_API_KEY is not set or is using the default placeholder. Internal API is insecure.")
        # In a production environment, you might want to deny all requests if the key is default.
        # For development, we might allow it but log a severe warning.
        # For this exercise, we'll proceed if it's default but ensure it's checked against.

    if not x_internal_api_key or x_internal_api_key != settings.INTERNAL_API_KEY:
        logger.warning(f"Invalid or missing internal API key. Provided key: '{x_internal_api_key}'")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing internal API key.")
    return True

# --- Background Task for Minting ---
def mint_wcas_in_background(deposit_id: int, recipient_address: str, amount: float, db_session: Session):
    """
    This function is executed in the background to handle the wCAS minting process.
    Supports both traditional minting and BYO-gas flow.
    """
    logger_prefix = f"[BackgroundTask] Minting for CasDeposit ID {deposit_id}: "
    try:
        logger.info(f"{logger_prefix}Starting background minting process.")
        
        # Get the CAS deposit to check fee model
        cas_deposit = crud.get_cas_deposit_by_id(db_session, deposit_id)
        if not cas_deposit:
            logger.error(f"{logger_prefix}CAS deposit not found")
            return
        
        # Check if this is a BYO-gas flow (direct_payment fee model)
        gas_payer_private_key = None
        
        if cas_deposit.fee_model == "direct_payment":
            # BYO-gas flow: check for gas deposit
            gas_deposit = crud.get_polygon_gas_deposit_by_cas_deposit_id(db_session, deposit_id)
            
            if not gas_deposit:
                logger.error(f"{logger_prefix}BYO-gas flow requires gas deposit, but none found")
                crud.update_cas_deposit_status_and_mint_hash(db_session, deposit_id, "mint_failed", received_amount=amount)
                return
            
            if gas_deposit.status != "funded":
                logger.error(f"{logger_prefix}Gas deposit not funded. Status: {gas_deposit.status}")
                crud.update_cas_deposit_status_and_mint_hash(db_session, deposit_id, "mint_failed", received_amount=amount)
                return
            
            # Use the gas deposit's private key
            try:
                gas_payer_private_key = crud.get_private_key_for_gas_deposit(gas_deposit)
                logger.info(f"{logger_prefix}Using BYO-gas flow with gas deposit ID {gas_deposit.id}")
            except Exception as e:
                logger.error(f"{logger_prefix}Failed to derive private key for gas deposit: {e}")
                crud.update_cas_deposit_status_and_mint_hash(db_session, deposit_id, "mint_failed", received_amount=amount)
                return
        else:
            logger.info(f"{logger_prefix}Using traditional minting flow (bridge pays gas)")
        
        # 1. Initialize PolygonService
        try:
            polygon_service = PolygonService()
            logger.info(f"{logger_prefix}PolygonService initialized successfully.")
        except Exception as service_exc:
            logger.error(f"{logger_prefix}Failed to initialize PolygonService: {service_exc}", exc_info=True)
            crud.update_cas_deposit_status_and_mint_hash(db_session, deposit_id, "mint_failed", received_amount=amount)
            return

        # 2. Call mint_wcas
        mint_tx_hash = polygon_service.mint_wcas(
            recipient_address=recipient_address,
            amount_cas=amount,
            custom_private_key=gas_payer_private_key
        )

        # 3. Update DB based on result
        if mint_tx_hash:
            # The polygon_service now waits for the receipt. 
            # If it returns a hash, we can be reasonably sure it was at least accepted.
            # A `None` return from the new implementation means it failed or timed out badly.
            logger.info(f"{logger_prefix}wCAS minting transaction processed. Final TxHash: {mint_tx_hash}")
            # We assume the service's logging provides details on success/failure.
            # Here we just mark it as submitted. A separate process could verify finality if needed.
            crud.update_cas_deposit_status_and_mint_hash(
                db=db_session,
                deposit_id=deposit_id,
                new_status="mint_submitted", # Or check receipt status from service if it were returned
                mint_tx_hash=mint_tx_hash,
                received_amount=amount
            )
            
            # Mark gas deposit as spent if this was BYO-gas flow
            if cas_deposit.fee_model == "direct_payment":
                gas_deposit = crud.get_polygon_gas_deposit_by_cas_deposit_id(db_session, deposit_id)
                if gas_deposit:
                    crud.update_polygon_gas_deposit_status(
                        db_session, 
                        gas_deposit.id, 
                        "spent"
                    )
                    logger.info(f"{logger_prefix}Marked gas deposit {gas_deposit.id} as spent")
        else:
            logger.error(f"{logger_prefix}PolygonService.mint_wcas did not return a transaction hash or failed.")
            crud.update_cas_deposit_status_and_mint_hash(db_session, deposit_id, "mint_failed", received_amount=amount)

    except Exception as e:
        logger.error(f"{logger_prefix}An unexpected error occurred in the background task: {e}", exc_info=True)
        crud.update_cas_deposit_status_and_mint_hash(db_session, deposit_id, "mint_failed", received_amount=amount)
    finally:
        db_session.close()


# --- Endpoint to initiate wCAS Minting ---
@router.post("/initiate_wcas_mint", response_model=schemas.WCASMintResponse, status_code=202)
async def initiate_wcas_mint(
    request: schemas.WCASMintRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key_verified: bool = Depends(verify_api_key) # API Key dependency
):
    """
    Internal endpoint called by the Cascoin watcher to initiate wCAS minting on Polygon
    after a Cascoin deposit has been confirmed.
    This endpoint now accepts the request and queues the minting process to run in the background.
    """
    logger_prefix = f"Minting for CasDeposit ID {request.cas_deposit_id}: "
    logger.info(f"{logger_prefix}Received request, preparing for background processing: {request.model_dump_json(indent=2)}")

    deposit = crud.get_cas_deposit_by_id(db, deposit_id=request.cas_deposit_id)

    if not deposit:
        logger.error(f"{logger_prefix}CasDeposit record not found.")
        raise HTTPException(status_code=404, detail=f"{logger_prefix}CasDeposit record not found.")

    valid_initial_statuses = ["cas_confirmed_pending_mint", "mint_trigger_failed", "mint_failed"]
    if deposit.status not in valid_initial_statuses:
        if deposit.mint_tx_hash and deposit.status in ["mint_submitted", "mint_confirmed_on_poly"]:
             logger.info(f"{logger_prefix}Minting already processed or in progress. Status: {deposit.status}, TxHash: {deposit.mint_tx_hash}")
             # Returning a 202 here might be confusing. A 200 OK might be better if skipping.
             return schemas.WCASMintResponse(
                status="skipped",
                message=f"Minting already processed or in progress. Status: {deposit.status}",
                polygon_mint_tx_hash=deposit.mint_tx_hash,
                cas_deposit_id=request.cas_deposit_id
            )
        logger.warning(f"{logger_prefix}Invalid deposit status for minting: {deposit.status}. Expected one of {valid_initial_statuses}.")
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Invalid deposit status for minting: {deposit.status}")

    if deposit.polygon_address.lower() != request.recipient_polygon_address.lower():
        logger.error(f"{logger_prefix}Recipient Polygon address mismatch. DB: {deposit.polygon_address}, Request: {request.recipient_polygon_address}")
        crud.update_cas_deposit_status_and_mint_hash(db, request.cas_deposit_id, "mint_failed", received_amount=deposit.received_amount)
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Recipient Polygon address mismatch.")

    if request.amount_to_mint <= 0:
        logger.error(f"{logger_prefix}Invalid mint amount: {request.amount_to_mint}. Must be positive.")
        crud.update_cas_deposit_status_and_mint_hash(db, request.cas_deposit_id, "mint_failed", received_amount=deposit.received_amount)
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Invalid mint amount. Must be positive.")

    if abs(request.amount_to_mint - deposit.received_amount) > 1e-9:
        logger.error(f"{logger_prefix}Mismatched mint amount. Requested: {request.amount_to_mint}, Expected from DB: {deposit.received_amount}")
        crud.update_cas_deposit_status_and_mint_hash(db, request.cas_deposit_id, "mint_failed", received_amount=deposit.received_amount)
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Mismatched mint amount.")

    # Add the long-running task to the background
    background_tasks.add_task(
        mint_wcas_in_background,
        deposit_id=deposit.id,
        recipient_address=deposit.polygon_address,
        amount=deposit.received_amount,
        db_session=db
    )
    
    logger.info(f"{logger_prefix}Minting process has been queued to run in the background.")

    # Immediately return an "accepted" response
    return schemas.WCASMintResponse(
        status="accepted",
        message="wCAS minting process has been accepted and is running in the background.",
        polygon_mint_tx_hash=None, # Hash is not known yet
        cas_deposit_id=request.cas_deposit_id
    )


# --- Endpoint to initiate CAS Release (from wCAS on Polygon) ---
@router.post("/initiate_cas_release", response_model=schemas.CASReleaseResponse)
async def initiate_cas_release(
    request: schemas.CASReleaseRequest,
    db: Session = Depends(get_db),
    api_key_verified: bool = Depends(verify_api_key) # API Key dependency
):
    """
    Internal endpoint called by the Polygon watcher to initiate CAS release
    after a wCAS deposit to the bridge has been confirmed on Polygon.
    """
    logger_prefix = f"CAS Release for Polygon Tx ID {request.polygon_transaction_id}: "
    logger.info(f"{logger_prefix}Received request: {request.model_dump_json(indent=2)}")

    poly_tx = crud.get_polygon_transaction_by_id(db, tx_id=request.polygon_transaction_id)

    if not poly_tx:
        logger.error(f"{logger_prefix}PolygonTransaction record not found.")
        # Cannot update status if record not found, but this indicates a logic error in caller or data issue.
        raise HTTPException(status_code=404, detail=f"{logger_prefix}PolygonTransaction record not found.")

    # Validations
    valid_initial_statuses = ["wcas_confirmed", "cas_release_trigger_failed", "cas_release_failed"]
    if poly_tx.status not in valid_initial_statuses:
        if poly_tx.cas_release_tx_hash and poly_tx.status in ["cas_release_submitted", "cas_released_on_cascoin"]:
            logger.info(f"{logger_prefix}CAS release already processed or in progress. Status: {poly_tx.status}, Cas TxHash: {poly_tx.cas_release_tx_hash}")
            return schemas.CASReleaseResponse(
                status="skipped",
                message=f"CAS release already processed or in progress. Status: {poly_tx.status}",
                cascoin_release_tx_hash=poly_tx.cas_release_tx_hash,
                polygon_transaction_id=request.polygon_transaction_id
            )
        logger.warning(f"{logger_prefix}Invalid PolygonTransaction status for CAS release: {poly_tx.status}. Expected one of {valid_initial_statuses}.")
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Invalid transaction status for CAS release: {poly_tx.status}")

    if poly_tx.user_cascoin_address_request.lower() != request.recipient_cascoin_address.lower():
        logger.error(f"{logger_prefix}Recipient Cascoin address mismatch. DB: {poly_tx.user_cascoin_address_request}, Request: {request.recipient_cascoin_address}")
        crud.update_polygon_transaction_status_and_cas_hash(db, poly_tx.id, "cas_release_failed")
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Recipient Cascoin address mismatch.")

    if poly_tx.user_cascoin_address_request == "UNKNOWN_NO_INTENTION":
        logger.error(f"{logger_prefix}Target Cascoin address is unknown (no prior intention logged). Cannot proceed with CAS release.")
        crud.update_polygon_transaction_status_and_cas_hash(db, poly_tx.id, "cas_release_failed") # Keep as failed
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Target Cascoin address is unknown. Cannot release CAS.")

    if request.amount_to_release <= 0:
        logger.error(f"{logger_prefix}Invalid release amount: {request.amount_to_release}. Must be positive.")
        crud.update_polygon_transaction_status_and_cas_hash(db, poly_tx.id, "cas_release_failed")
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Invalid release amount. Must be positive.")

    if abs(request.amount_to_release - poly_tx.amount) > 1e-9: # Tolerance for float comparison
        logger.error(f"{logger_prefix}Mismatched release amount. Requested: {request.amount_to_release}, Expected from DB: {poly_tx.amount}")
        crud.update_polygon_transaction_status_and_cas_hash(db, poly_tx.id, "cas_release_failed")
        raise HTTPException(status_code=400, detail=f"{logger_prefix}Mismatched release amount.")

    # Initialize CascoinService
    try:
        cascoin_service = CascoinService()
        logger.info(f"{logger_prefix}CascoinService initialized successfully.")
    except Exception as e:
        logger.error(f"{logger_prefix}Failed to initialize CascoinService: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{logger_prefix}Failed to initialize CascoinService: {str(e)}")

    # Call CascoinService to send CAS
    try:
        logger.info(f"{logger_prefix}Calling CascoinService.send_cas to {poly_tx.user_cascoin_address_request} with amount {poly_tx.amount}")
        cas_tx_hash = cascoin_service.send_cas(
            to_address=poly_tx.user_cascoin_address_request,
            amount=poly_tx.amount
        )

        if cas_tx_hash:
            logger.info(f"{logger_prefix}CAS release transaction submitted to Cascoin. TxHash: {cas_tx_hash}")
            crud.update_polygon_transaction_status_and_cas_hash(
                db=db,
                polygon_tx_id=poly_tx.id,
                new_status="cas_release_submitted",
                cas_tx_hash=cas_tx_hash
            )
            return schemas.CASReleaseResponse(
                status="success",
                message="CAS release transaction submitted to Cascoin.",
                cascoin_release_tx_hash=cas_tx_hash,
                polygon_transaction_id=request.polygon_transaction_id
            )
        else:
            logger.error(f"{logger_prefix}CascoinService.send_cas did not return a transaction hash.")
            crud.update_polygon_transaction_status_and_cas_hash(db, poly_tx.id, "cas_release_failed")
            return schemas.CASReleaseResponse(
                status="error",
                message="Failed to submit CAS release transaction. CascoinService did not return a hash.",
                cascoin_release_tx_hash=None,
                polygon_transaction_id=request.polygon_transaction_id
            )
    except Exception as e:
        logger.error(f"{logger_prefix}Unexpected error during CAS release: {e}", exc_info=True)
        crud.update_polygon_transaction_status_and_cas_hash(db, poly_tx.id, "cas_release_failed")
        raise HTTPException(status_code=500, detail=f"{logger_prefix}An unexpected error occurred: {str(e)}")


# --- BYO-Gas Endpoints ---

@router.post("/request_polygon_gas_address", response_model=schemas.PolygonGasDepositResponse)
def request_polygon_gas_address(
    request: schemas.PolygonGasDepositRequest, 
    db: Session = Depends(get_db),
    api_key_verified: bool = Depends(verify_api_key)
):
    """
    Internal endpoint to create a polygon gas deposit address for BYO-gas flow.
    Called when a CAS deposit with direct_payment fee model is detected.
    """
    logger_prefix = f"Gas Address Request for CAS Deposit {request.cas_deposit_id}: "
    logger.info(f"{logger_prefix}Received request: {request.model_dump_json(indent=2)}")
    
    # Validate the CAS deposit exists
    cas_deposit = crud.get_cas_deposit_by_id(db, request.cas_deposit_id)
    if not cas_deposit:
        logger.error(f"{logger_prefix}CAS deposit not found")
        raise HTTPException(status_code=404, detail="CasDeposit record not found")
    
    # Validate that this CAS deposit uses direct payment fee model
    if cas_deposit.fee_model != "direct_payment":
        logger.error(f"{logger_prefix}Wrong fee model: {cas_deposit.fee_model}")
        raise HTTPException(status_code=400, detail="Gas address can only be requested for direct_payment fee model")
    
    # Check if gas deposit already exists for this CAS deposit
    existing_gas_deposit = crud.get_polygon_gas_deposit_by_cas_deposit_id(db, request.cas_deposit_id)
    if existing_gas_deposit:
        logger.info(f"{logger_prefix}Returning existing gas deposit: {existing_gas_deposit.polygon_gas_address}")
        return schemas.PolygonGasDepositResponse(
            status="existing",
            polygon_gas_address=existing_gas_deposit.polygon_gas_address,
            required_matic=existing_gas_deposit.required_matic,
            hd_index=existing_gas_deposit.hd_index,
            cas_deposit_id=existing_gas_deposit.cas_deposit_id
        )
    
    # Validate MATIC amount
    if request.required_matic <= 0:
        logger.error(f"{logger_prefix}Invalid MATIC amount: {request.required_matic}")
        raise HTTPException(status_code=400, detail="MATIC amount must be positive")
    
    # Create new gas deposit record
    try:
        gas_deposit = crud.create_polygon_gas_deposit(
            db=db,
            cas_deposit_id=request.cas_deposit_id,
            matic_required=request.required_matic
        )
        
        if not gas_deposit:
            logger.error(f"{logger_prefix}Failed to create gas deposit")
            raise HTTPException(status_code=500, detail="Could not create polygon gas deposit address")
        
        logger.info(f"{logger_prefix}Created new gas deposit: {gas_deposit.polygon_gas_address}")
        return schemas.PolygonGasDepositResponse(
            status="success",
            polygon_gas_address=gas_deposit.polygon_gas_address,
            required_matic=gas_deposit.required_matic,
            hd_index=gas_deposit.hd_index,
            cas_deposit_id=gas_deposit.cas_deposit_id
        )
        
    except Exception as e:
        logger.error(f"{logger_prefix}Error creating gas deposit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create gas deposit: {str(e)}")


# --- Notification Endpoints for Websocket Updates ---
@router.post("/notify_deposit_update")
async def notify_deposit_update(
    request: dict,
    db: Session = Depends(get_db),
    api_key_verified: bool = Depends(verify_api_key)
):
    """
    Internal endpoint called by watchers to trigger websocket notifications for deposit updates
    """
    try:
        from backend.api.websocket_api import notify_cas_deposit_update
        deposit_id = request.get("deposit_id")
        if not deposit_id:
            raise HTTPException(status_code=400, detail="deposit_id is required")
        
        await notify_cas_deposit_update(deposit_id, db)
        return {"status": "success", "message": "Websocket notification sent"}
    except Exception as e:
        logger.error(f"Error sending websocket notification for deposit {request.get('deposit_id')}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


@router.post("/notify_polygon_transaction_update")
async def notify_polygon_transaction_update(
    request: dict,
    db: Session = Depends(get_db),
    api_key_verified: bool = Depends(verify_api_key)
):
    """
    Internal endpoint called by watchers to trigger websocket notifications for polygon transaction updates
    """
    try:
        from backend.api.websocket_api import notify_polygon_transaction_update
        polygon_transaction_id = request.get("polygon_transaction_id")
        if not polygon_transaction_id:
            raise HTTPException(status_code=400, detail="polygon_transaction_id is required")
        
        await notify_polygon_transaction_update(polygon_transaction_id, db)
        return {"status": "success", "message": "Websocket notification sent"}
    except Exception as e:
        logger.error(f"Error sending websocket notification for polygon tx {request.get('polygon_transaction_id')}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")
