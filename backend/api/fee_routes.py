"""
API routes for fee calculation and estimation.
"""

from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.services.fee_service import fee_service
from backend.services.matic_fee_service import matic_fee_service

router = APIRouter(prefix="/api/fees", tags=["fees"])

class FeeEstimateRequest(BaseModel):
    amount: str
    operation: str  # 'cas_to_wcas' or 'wcas_to_cas'
    fee_model: Optional[str] = 'direct_payment'  # 'direct_payment' or 'deducted'

class FeeEstimateResponse(BaseModel):
    input_amount: str
    output_amount: str
    fee_percentage: str
    fee_breakdown: dict
    operation: str
    fee_model: str
    is_valid: bool
    error_message: Optional[str] = None
    # Optional fields that may or may not be present depending on fee model
    total_fees: Optional[str] = None
    bridge_fee: Optional[str] = None
    matic_fee_required: Optional[str] = None
    cas_network_fee: Optional[str] = None
    user_pays_gas: Optional[bool] = None

@router.post("/estimate", response_model=FeeEstimateResponse)
async def estimate_fees(request: FeeEstimateRequest):
    """
    Estimate fees for a bridge operation.
    
    Args:
        request: Fee estimation request with amount and operation type
        
    Returns:
        Detailed fee breakdown and net amounts
    """
    try:
        # Validate amount format and value first
        try:
            amount = Decimal(request.amount)
        except (ValueError, TypeError, ArithmeticError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid amount format: {str(e)}")
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        # Validate operation type
        if request.operation not in ['cas_to_wcas', 'wcas_to_cas']:
            raise HTTPException(
                status_code=400, 
                detail="Operation must be 'cas_to_wcas' or 'wcas_to_cas'"
            )
        
        # Validate fee model
        if request.fee_model and request.fee_model not in ['direct_payment', 'deducted']:
            raise HTTPException(
                status_code=400,
                detail="Fee model must be 'direct_payment' or 'deducted'"
            )
        
        # Get fee estimate
        fee_estimate = fee_service.get_fee_estimate_for_user(amount, request.operation, request.fee_model)
        
        # Validate minimum amount
        is_valid, error_message = fee_service.validate_minimum_amount(amount, request.operation, request.fee_model)
        
        return FeeEstimateResponse(
            **fee_estimate,
            is_valid=is_valid,
            error_message=error_message
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions to maintain status codes
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid amount format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fee calculation error: {str(e)}")

@router.get("/quick-estimate")
async def quick_fee_estimate(
    amount: str = Query(..., description="Amount to bridge"),
    operation: str = Query(..., description="Operation type: cas_to_wcas or wcas_to_cas"),
    fee_model: str = Query('direct_payment', description="Fee model: direct_payment or deducted")
):
    """
    Quick fee estimate endpoint for simple queries.
    
    Query Parameters:
        amount: Amount to bridge
        operation: 'cas_to_wcas' or 'wcas_to_cas'
        
    Returns:
        Basic fee information
    """
    try:
        amount_decimal = Decimal(amount)
        
        if amount_decimal <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        if operation not in ['cas_to_wcas', 'wcas_to_cas']:
            raise HTTPException(
                status_code=400, 
                detail="Operation must be 'cas_to_wcas' or 'wcas_to_cas'"
            )
        
        if fee_model not in ['direct_payment', 'deducted']:
            raise HTTPException(
                status_code=400,
                detail="Fee model must be 'direct_payment' or 'deducted'"
            )
        
        fee_estimate = fee_service.get_fee_estimate_for_user(amount_decimal, operation, fee_model)
        is_valid, error_message = fee_service.validate_minimum_amount(amount_decimal, operation, fee_model)
        
        # Get total fees - handle different fee models
        total_fees = fee_estimate.get("total_fees", "0")
        if not total_fees or total_fees == "0":
            # For direct payment model, calculate from available fees
            bridge_fee = fee_estimate.get("bridge_fee", "0")
            cas_network_fee = fee_estimate.get("cas_network_fee", "0")
            try:
                total_fees = str(Decimal(bridge_fee) + Decimal(cas_network_fee))
            except:
                total_fees = bridge_fee
        
        return {
            "input_amount": fee_estimate["input_amount"],
            "output_amount": fee_estimate["output_amount"],
            "total_fees": total_fees,
            "fee_percentage": fee_estimate["fee_percentage"],
            "is_valid": is_valid,
            "error_message": error_message
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid amount format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fee calculation error: {str(e)}")

@router.get("/config")
async def get_fee_config():
    """
    Get current fee configuration.
    
    Returns:
        Current fee rates and limits
    """
    return {
        "bridge_fee_percentage": str(fee_service.bridge_fee_percentage * 100),  # Convert to percentage
        "min_cas_fee": str(fee_service.min_cas_fee),
        "max_fee_percentage": str(fee_service.max_fee_percentage * 100),  # Convert to percentage
        "estimated_polygon_fee_cas": str(fee_service._estimate_polygon_fee_in_cas()),
        "currency": "CAS",
        "fee_models": ["direct_payment", "deducted"],
        "default_fee_model": fee_service.fee_model
    }

@router.get("/matic-options/{user_address}")
async def get_matic_fee_options(
    user_address: str,
    operation: str = Query(..., description="Bridge operation: mint_wcas, burn_wcas, transfer_wcas")
):
    """
    Get MATIC fee payment options for a user.
    
    Args:
        user_address: User's Polygon address
        operation: Type of bridge operation
        
    Returns:
        Available fee payment methods including token conversion options
    """
    try:
        if operation not in ['mint_wcas', 'burn_wcas', 'transfer_wcas']:
            raise HTTPException(
                status_code=400,
                detail="Operation must be 'mint_wcas', 'burn_wcas', or 'transfer_wcas'"
            )
        
        options = matic_fee_service.get_user_fee_options(user_address, operation)
        return options
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting fee options: {str(e)}")

@router.post("/calculate-token-to-matic")
async def calculate_token_to_matic_conversion(
    token_type: str = Query(..., description="Token type: wCAS or CAS"),
    gas_estimate: int = Query(..., description="Estimated gas units needed"),
    gas_price_gwei: Optional[float] = Query(None, description="Gas price in Gwei (optional)")
):
    """
    Calculate how much wCAS/CAS is needed to cover MATIC fees.
    
    Query Parameters:
        token_type: 'wCAS' or 'CAS'
        gas_estimate: Gas units needed for transaction
        gas_price_gwei: Gas price in Gwei (optional, will estimate if not provided)
        
    Returns:
        Token conversion details for MATIC fees
    """
    try:
        if token_type.upper() not in ['WCAS', 'CAS']:
            raise HTTPException(status_code=400, detail="Token type must be 'wCAS' or 'CAS'")
        
        gas_price_wei = None
        if gas_price_gwei:
            from web3 import Web3
            gas_price_wei = Web3.to_wei(gas_price_gwei, 'gwei')
        
        conversion_details = matic_fee_service.calculate_matic_fee_in_tokens(
            gas_estimate, token_type, gas_price_wei
        )
        
        return conversion_details
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion calculation error: {str(e)}")

@router.get("/exchange-rates")
async def get_current_exchange_rates():
    """
    Get current exchange rates for token-to-MATIC conversions.
    
    Returns:
        Current exchange rates and conversion fees
    """
    return {
        "matic_to_cas_rate": str(matic_fee_service.matic_to_cas_rate),
        "wcas_to_matic_rate": str(matic_fee_service.wcas_to_matic_rate),
        "conversion_fee_percentage": str(matic_fee_service.conversion_fee_percentage * 100),
        "last_updated": "real_time",  # In production, include actual timestamp
        "note": "These are example rates. In production, fetch from price oracles."
    } 