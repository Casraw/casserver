from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend import crud
from backend.database import get_db
from backend.services.polygon_service import PolygonService
from pydantic import BaseModel, Field
import logging
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

polygon_service_instance: Optional[PolygonService] = None
try:
    polygon_service_instance = PolygonService()
    logger.info("PolygonService initialized successfully for internal_api.")
except Exception as e:
    logger.error(f"CRITICAL: Failed to initialize PolygonService for internal_api: {e}. Minting endpoints will fail.", exc_info=True)

class MintRequest(BaseModel):
    cas_deposit_id: int = Field(..., description="ID of the CasDeposit record in the bridge database")

class MintResponse(BaseModel):
    message: str
    cas_deposit_id: int
    status: str
    polygon_tx_hash: Optional[str] = None

@router.post("/initiate_wcas_mint", response_model=MintResponse, tags=["Internal Bridge Operations"])
async def initiate_wcas_mint(request: MintRequest, db: Session = Depends(get_db)):
    logger.info(f"Received internal request to mint wCAS for CasDeposit ID: {request.cas_deposit_id}")

    if not polygon_service_instance:
        logger.error("PolygonService not available. Cannot process minting request.")
        raise HTTPException(status_code=503, detail="Minting service is currently unavailable.")

    deposit = crud.get_cas_deposit_by_id(db, request.cas_deposit_id)
    if not deposit:
        raise HTTPException(status_code=404, detail=f"Cascoin deposit record ID {request.cas_deposit_id} not found.")

    if deposit.status not in ["confirmed_cas", "mint_trigger_failed", "minting_failed"]:
        raise HTTPException(status_code=400, detail=f"Deposit status '{deposit.status}' not valid for minting.")

    if deposit.received_amount is None or deposit.received_amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit received_amount is missing or zero.")

    recipient_polygon_address = deposit.polygon_address
    amount_cas_float = deposit.received_amount

    crud.update_cas_deposit_status_and_mint_hash(db, deposit.id, "minting_initiated")
    logger.info(f"CasDeposit ID {deposit.id} status 'minting_initiated'. Minting {amount_cas_float} wCAS for {recipient_polygon_address}.")

    tx_hash = polygon_service_instance.mint_wcas(
        to_address=recipient_polygon_address,
        amount_cas_float=amount_cas_float
    )

    if tx_hash:
        updated_deposit = crud.update_cas_deposit_status_and_mint_hash(db, deposit.id, "minting_submitted", tx_hash)
        status_after_update = updated_deposit.status if updated_deposit else "minting_submitted"
        logger.info(f"wCAS mint tx submitted for CasDeposit ID {deposit.id}. Tx Hash: {tx_hash}. Status: {status_after_update}")
        return MintResponse(
            message="wCAS minting transaction successfully submitted.",
            cas_deposit_id=deposit.id,
            status=status_after_update,
            polygon_tx_hash=tx_hash
        )
    else:
        updated_deposit = crud.update_cas_deposit_status_and_mint_hash(db, deposit.id, "minting_failed")
        status_after_update = updated_deposit.status if updated_deposit else "minting_failed"
        logger.error(f"wCAS minting failed for CasDeposit ID {deposit.id}. Status: {status_after_update}")
        raise HTTPException(status_code=500, detail="Failed to submit wCAS minting transaction.")
