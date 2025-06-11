from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from database import models # This should point to database/models.py
from backend.schemas import UserCreate #, CasDepositCreate # Using CasDepositRequest for input now
import uuid
from typing import Optional # Added for type hinting

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
def create_cas_deposit_record(db: Session, polygon_address: str) -> models.CasDeposit:
    # THIS IS A PLACEHOLDER FOR CASCOIN ADDRESS GENERATION.
    # Real Cascoin address generation is complex and requires managing private keys.
    # It should ideally be done by interacting with a Cascoin node/wallet service.
    unique_part = str(uuid.uuid4().hex[:12]) # Made slightly longer for demo
    generated_cas_address = f"cas_dep_{unique_part}"

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
        if received_amount is not None:
             deposit.received_amount = received_amount
        deposit.updated_at = func.now()
        db.commit()
        db.refresh(deposit)
        return deposit
    return None
