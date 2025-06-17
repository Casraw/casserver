from pydantic import BaseModel, Field
from typing import Optional
import datetime

# User Schemas
class UserBase(BaseModel):
    cascoin_address: Optional[str] = None
    polygon_address: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Bridge Configuration Information ---
class BridgeConfigResponse(BaseModel):
    bridge_wcas_deposit_address: str

    class Config:
        from_attributes = True

# --- Schemas for wCAS to CAS Return Intention (Polygon -> Cascoin) ---

class WCASReturnIntentionRequest(BaseModel):
    user_polygon_address: str = Field(..., description="The Polygon address the user will send wCAS from.")
    target_cascoin_address: str = Field(..., description="The Cascoin address to receive CAS.")
    bridge_amount: float = Field(..., description="Amount of wCAS to bridge.")
    fee_model: str = Field(..., description="Fee model: 'direct_payment' or 'deducted'.")

class WCASReturnIntentionResponse(BaseModel):
    id: int
    user_polygon_address: str
    target_cascoin_address: str
    bridge_address: str
    bridge_amount: float
    fee_model: str
    status: str # Should be "pending_deposit" initially
    message: str = "Intention registered. Please deposit wCAS to the bridge address from your specified Polygon address."
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Internal API Schemas ---

# For wCAS Minting (Cascoin -> Polygon)
class WCASMintRequest(BaseModel):
    cas_deposit_id: int
    amount_to_mint: float
    recipient_polygon_address: str
    cas_deposit_address: str # For logging/verification

class WCASMintResponse(BaseModel):
    status: str
    message: str
    polygon_mint_tx_hash: Optional[str] = None
    cas_deposit_id: int

# For CAS Release (Polygon -> Cascoin)
class CASReleaseRequest(BaseModel):
    polygon_transaction_id: int
    amount_to_release: float # Should match the wCAS amount from PolygonTransaction
    recipient_cascoin_address: str # Should match user_cascoin_address_request from PolygonTransaction

class CASReleaseResponse(BaseModel):
    status: str
    message: str
    cascoin_release_tx_hash: Optional[str] = None
    polygon_transaction_id: int

# CasDeposit Schemas
class CasDepositRequest(BaseModel): # Renamed from CasDepositBase for clarity
    polygon_address: str = Field(..., description="User's Polygon address where wCAS will be minted.")

# CasDepositCreate is more for internal use if fields differ from request
# class CasDepositCreate(CasDepositBase):
# pass

class CasDepositResponse(BaseModel):
    cascoin_deposit_address: str
    polygon_address: str
    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# PolygonTransaction Schemas
class WCASDepositRequest(BaseModel):
    user_cascoin_address: str = Field(..., description="The Cascoin address to receive CAS.")

class WCASDepositResponse(BaseModel):
    bridge_wcas_deposit_address: str
    user_cascoin_address: str # Echo back for confirmation
    message: str = "Deposit wCAS to this address. Your CAS will be sent to the provided Cascoin address after confirmation."

    class Config:
        from_attributes = True
