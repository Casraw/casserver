from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend import crud
from backend import schemas # Explicitly import schemas
from backend.database import get_db
from backend.config import settings # Import settings to get the bridge address

router = APIRouter()

@router.post("/request_cascoin_deposit_address", response_model=schemas.CasDepositResponse)
def request_cascoin_deposit_address(
    request: schemas.CasDepositRequest, db: Session = Depends(get_db)
):
    if not request.polygon_address or not request.polygon_address.startswith("0x") or len(request.polygon_address) != 42: # Basic check
        raise HTTPException(status_code=400, detail="Valid Ethereum Polygon address (0x...) is required.")

    deposit_record = crud.create_cas_deposit_record(db=db, polygon_address=request.polygon_address)
    if not deposit_record:
        raise HTTPException(status_code=500, detail="Could not generate Cascoin deposit address record.")

    return schemas.CasDepositResponse(
        cascoin_deposit_address=deposit_record.cascoin_deposit_address,
        polygon_address=deposit_record.polygon_address,
        status=deposit_record.status,
        created_at=deposit_record.created_at
    )

@router.post("/request_wcas_deposit_address", response_model=schemas.WCASDepositResponse)
def request_wcas_deposit_address(
    request: schemas.WCASDepositRequest, db: Session = Depends(get_db) # db might be used to log the request
):
    # Add specific validation for Cascoin addresses if possible (e.g., prefix, length)
    if not request.user_cascoin_address or len(request.user_cascoin_address) < 20: # Placeholder validation
        raise HTTPException(status_code=400, detail="Valid Cascoin address is required.")

    # Log the user's intent (optional, but good for tracking)
    # crud.log_user_intent_for_wcas_deposit(db, cascoin_address=request.user_cascoin_address)

    return schemas.WCASDepositResponse(
        bridge_wcas_deposit_address=settings.BRIDGE_WCAS_DEPOSIT_ADDRESS,
        user_cascoin_address=request.user_cascoin_address,
        message=f"Deposit wCAS to {settings.BRIDGE_WCAS_DEPOSIT_ADDRESS}. Your CAS will be sent to {request.user_cascoin_address} after confirmation."
    )
