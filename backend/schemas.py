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
