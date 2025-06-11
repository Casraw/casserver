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

@router.post("/initiate_wcas_to_cas_return", response_model=schemas.WCASReturnIntentionResponse)
def initiate_wcas_to_cas_return(
    request: schemas.WCASReturnIntentionRequest, db: Session = Depends(get_db)
):
    """
    Allows a user to register their intention to send wCAS to the bridge
    and specify the target Cascoin address for receiving CAS.
    """
    # Basic validation for Polygon address
    if not request.user_polygon_address or not request.user_polygon_address.startswith("0x") or len(request.user_polygon_address) != 42:
        raise HTTPException(status_code=400, detail="Valid Ethereum Polygon address (0x...) is required for user_polygon_address.")

    # Basic validation for Cascoin address (can be improved with regex or checksum validation)
    if not request.target_cascoin_address or len(request.target_cascoin_address) < 20: # Placeholder
        raise HTTPException(status_code=400, detail="Valid Cascoin address is required for target_cascoin_address.")

    try:
        # Optional: Check if there's already an active intention for this polygon address to prevent spamming.
        # existing_intention = crud.get_pending_wcas_return_intention_by_poly_address(db, user_polygon_address=request.user_polygon_address)
        # if existing_intention:
        #     # You might want to allow overriding or just return the existing one, or error out.
        #     # For now, let's allow creating a new one. Old ones might expire or be cleaned up.
        #     pass

        intention_record = crud.create_wcas_return_intention(db=db, intention_request=request)
        if not intention_record:
            # This case should ideally not happen if DB is up, but good to have.
            raise HTTPException(status_code=500, detail="Could not register wCAS to CAS return intention.")

        return schemas.WCASReturnIntentionResponse(
            id=intention_record.id,
            user_polygon_address=intention_record.user_polygon_address,
            target_cascoin_address=intention_record.target_cascoin_address,
            status=intention_record.status,
            created_at=intention_record.created_at
            # The message field from WCASReturnIntentionResponse has a default value.
        )
    except Exception as e:
        # Log the exception e
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
