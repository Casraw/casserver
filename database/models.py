from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
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

    mint_tx_hash = Column(String, nullable=True)

    user = relationship("User", back_populates="deposits")

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

    cas_release_tx_hash = Column(String, nullable=True)

# Function to create tables
def create_db_tables():
    Base.metadata.create_all(bind=engine)
