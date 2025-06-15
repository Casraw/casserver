from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from database import models # This should point to database/models.py
# from backend.schemas import UserCreate # Not used in this version of create_cas_deposit_record
# import uuid # No longer needed for Cascoin address generation
from typing import Optional

from backend.services.cascoin_service import CascoinService

# Instantiate the CascoinService
# This assumes CascoinService is safe to be instantiated globally.
# If it had per-request state or needed more complex setup, consider dependency injection.
cascoin_service = CascoinService()

# User CRUD (Not directly used by current bridge endpoints but good for future)
def get_user_by_polygon_address(db: Session, polygon_address: str):
    return db.query(models.User).filter(models.User.polygon_address == polygon_address).first()

def create_user_with_polygon_address(db: Session, polygon_address: str) -> models.User:
    db_user = models.User(polygon_address=polygon_address)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# CasDeposit CRUD
def create_cas_deposit_record(db: Session, polygon_address: str) -> models.CasDeposit | None:
    # Generate a new Cascoin address using the CascoinService
    # We use the polygon_address as a label for the Cascoin address.
    # This can help in tracking which deposit address belongs to which Polygon user on the Cascoin node side.
    generated_cas_address = cascoin_service.get_new_address(account=polygon_address)

    if not generated_cas_address:
        # Failed to generate a Cascoin address.
        # The CascoinService's get_new_address method should have logged the specific error.
        # Returning None indicates failure to the calling API endpoint.
        return None

    # Optional: Link to or create a User record
    # user = get_user_by_polygon_address(db, polygon_address=polygon_address)
    # if not user:
    #     user = create_user_with_polygon_address(db, polygon_address=polygon_address)
    # user_id = user.id

    db_deposit = models.CasDeposit(
        # user_id=user_id, # If linking to user table
        polygon_address=polygon_address,
        cascoin_deposit_address=generated_cas_address
    )
    db.add(db_deposit)
    db.commit()
    db.refresh(db_deposit)
    return db_deposit

def get_cas_deposit_by_deposit_address(db: Session, deposit_address: str) -> Optional[models.CasDeposit]:
    return db.query(models.CasDeposit).filter(models.CasDeposit.cascoin_deposit_address == deposit_address).first()

# PolygonTransaction CRUD (to be expanded by Polygon watcher)
def log_pending_wcas_deposit(db: Session, user_cascoin_address: str, from_address: str, to_address: str, amount: float, polygon_tx_hash: str) -> models.PolygonTransaction:
    db_tx = models.PolygonTransaction(
        user_cascoin_address_request=user_cascoin_address,
        from_address=from_address,
        to_address=to_address,
        amount=amount,
        polygon_tx_hash=polygon_tx_hash,
        status="pending_confirmation" # Initial status when watcher picks it up
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx

# Added for wCAS Minting Service
def get_cas_deposit_by_id(db: Session, deposit_id: int) -> Optional[models.CasDeposit]:
    return db.query(models.CasDeposit).filter(models.CasDeposit.id == deposit_id).first()

def update_cas_deposit_status_and_mint_hash(
    db: Session,
    deposit_id: int,
    new_status: str,
    mint_tx_hash: Optional[str] = None,
    received_amount: Optional[float] = None
) -> Optional[models.CasDeposit]:
    deposit = get_cas_deposit_by_id(db, deposit_id)
    if deposit:
        deposit.status = new_status
        if mint_tx_hash:
            deposit.mint_tx_hash = mint_tx_hash
        if received_amount is not None: # Ensure this logic is correct for how amounts are updated
             deposit.received_amount = received_amount
        deposit.updated_at = func.now()
        db.commit()
        db.refresh(deposit)
        return deposit
    return None

# --- CRUD for WcasToCasReturnIntention ---

def create_wcas_return_intention(db: Session, intention_request: models.WcasToCasReturnIntention) -> models.WcasToCasReturnIntention:
    """
    Creates a new WcasToCasReturnIntention record.
    The intention_request here is expected to be a schemas.WCASReturnIntentionRequest Pydantic model.
    """
    db_intention = models.WcasToCasReturnIntention(
        user_polygon_address=intention_request.user_polygon_address,
        target_cascoin_address=intention_request.target_cascoin_address,
        status="pending_deposit" # Initial status
    )
    db.add(db_intention)
    db.commit()
    db.refresh(db_intention)
    return db_intention

def get_pending_wcas_return_intention_by_poly_address(db: Session, user_polygon_address: str) -> Optional[models.WcasToCasReturnIntention]:
    """
    Fetches the most recent WcasToCasReturnIntention for a given user_polygon_address
    with status == "pending_deposit", ordered by created_at descending.
    This helps the watcher find the relevant intention when a wCAS deposit is detected.
    """
    return db.query(models.WcasToCasReturnIntention)\
        .filter(models.WcasToCasReturnIntention.user_polygon_address == user_polygon_address)\
        .filter(models.WcasToCasReturnIntention.status == "pending_deposit")\
        .order_by(models.WcasToCasReturnIntention.created_at.desc())\
        .first()

def update_wcas_return_intention_status(db: Session, intention_id: int, new_status: str) -> Optional[models.WcasToCasReturnIntention]:
    """
    Updates the status of a WcasToCasReturnIntention record by its ID.
    """
    intention = db.query(models.WcasToCasReturnIntention).filter(models.WcasToCasReturnIntention.id == intention_id).first()
    if intention:
        intention.status = new_status
        intention.updated_at = func.now()
        db.commit()
        db.refresh(intention)
        return intention
    return None

# --- CRUD for PolygonTransaction related to CAS Release ---

def get_polygon_transaction_by_id(db: Session, tx_id: int) -> Optional[models.PolygonTransaction]:
    """
    Fetches a PolygonTransaction record by its primary key.
    """
    return db.query(models.PolygonTransaction).filter(models.PolygonTransaction.id == tx_id).first()

def update_polygon_transaction_status_and_cas_hash(
    db: Session,
    polygon_tx_id: int,
    new_status: str,
    cas_tx_hash: Optional[str] = None
) -> Optional[models.PolygonTransaction]:
    """
    Updates the status and cas_release_tx_hash of a PolygonTransaction record.
    """
    poly_tx = db.query(models.PolygonTransaction).filter(models.PolygonTransaction.id == polygon_tx_id).first()
    if poly_tx:
        poly_tx.status = new_status
        if cas_tx_hash: # Only update if a new hash is provided
            poly_tx.cas_release_tx_hash = cas_tx_hash
        poly_tx.updated_at = func.now()
        db.commit()
        db.refresh(poly_tx)
        return poly_tx
    return None
