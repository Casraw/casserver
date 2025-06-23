from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func # For default timestamp

from backend.database import Base, engine # Import Base from backend.database

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    cascoin_address = Column(String, unique=True, index=True, nullable=True)
    polygon_address = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    deposits = relationship("CasDeposit", back_populates="user")

class CasDeposit(Base):
    __tablename__ = "cas_deposits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    polygon_address = Column(String, index=True, nullable=False) # User's polygon address
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

    user = relationship("User", back_populates="deposits")
    processed_cascoin_txs = relationship("ProcessedCascoinTxs", back_populates="cas_deposit")

class ProcessedCascoinTxs(Base):
    __tablename__ = "processed_cascoin_txs"

    id = Column(Integer, primary_key=True, index=True)
    cascoin_txid = Column(String, index=True, nullable=False)
    cascoin_vout_index = Column(Integer, nullable=False)
    cas_deposit_id = Column(Integer, ForeignKey("cas_deposits.id"), nullable=False)
    amount_received = Column(Float, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    cas_deposit = relationship("CasDeposit", back_populates="processed_cascoin_txs")

    __table_args__ = (UniqueConstraint('cascoin_txid', 'cascoin_vout_index', name='_cascoin_txid_vout_uc'),)

class PolygonTransaction(Base):
    __tablename__ = "polygon_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_cascoin_address_request = Column(String, index=True, nullable=False)
    from_address = Column(String, index=True, nullable=False)
    to_address = Column(String, index=True, nullable=False) # Bridge's wCAS deposit address
    amount = Column(Float, nullable=False)
    polygon_tx_hash = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Added fields for confirmation tracking
    current_confirmations = Column(Integer, default=0)
    required_confirmations = Column(Integer, default=12)

    cas_release_tx_hash = Column(String, nullable=True)

class WcasToCasReturnIntention(Base):
    __tablename__ = "wcas_to_cas_return_intentions"
    id = Column(Integer, primary_key=True, index=True)
    user_polygon_address = Column(String, index=True, nullable=False) # Address sending wCAS
    target_cascoin_address = Column(String, nullable=False)    # Cascoin address to receive CAS
    bridge_amount = Column(Float, nullable=False)  # Amount of wCAS to bridge
    fee_model = Column(String, nullable=False)  # Fee model: 'direct_payment' or 'deducted'
    status = Column(String, default="pending_deposit", index=True) # e.g., pending_deposit, deposit_detected, processed, expired
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PolygonGasDeposit(Base):
    __tablename__ = "polygon_gas_deposits"
    
    id = Column(Integer, primary_key=True, index=True)
    cas_deposit_id = Column(Integer, ForeignKey("cas_deposits.id"), nullable=False)
    polygon_gas_address = Column(String, unique=True, index=True, nullable=False)  # EOA controlled by bridge
    required_matic = Column(Float, nullable=False)  # What the fee service quoted
    received_matic = Column(Float, default=0.0)     # What was actually received
    status = Column(String, default="pending", index=True)  # pending, funded, spent, expired
    hd_index = Column(Integer, nullable=False)       # HD derivation index for this address
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship back to the CAS deposit
    cas_deposit = relationship("CasDeposit", backref="gas_deposits")

# Function to create tables
def create_db_tables():
    Base.metadata.create_all(bind=engine)
