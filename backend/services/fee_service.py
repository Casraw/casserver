"""
Fee Service for handling transaction fees in the bridge system.
Supports multiple fee models: deducted fees vs direct MATIC payment.
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple
from web3 import Web3

from backend.config import settings

logger = logging.getLogger(__name__)

class FeeService:
    """Service for calculating and handling fees in bridge operations."""
    
    def __init__(self):
        # Fee percentages (can be made configurable via settings)
        self.bridge_fee_percentage = Decimal('0.001')  # 0.1% bridge fee
        
        # Minimum fees to cover network costs
        self.min_polygon_fee_wei = Web3.to_wei(0.01, 'ether')  # 0.01 MATIC equivalent in gas
        self.min_cas_fee = Decimal('0.001')  # 0.001 CAS minimum fee
        
        # Maximum fees to prevent excessive deductions
        self.max_fee_percentage = Decimal('0.05')  # 5% maximum fee
        
        # Fee model: 'deducted' or 'direct_payment'
        self.fee_model = 'direct_payment'  # Changed default to direct payment
    
    def set_fee_model(self, model: str):
        """Set the fee model: 'deducted' or 'direct_payment'"""
        if model not in ['deducted', 'direct_payment']:
            raise ValueError("Fee model must be 'deducted' or 'direct_payment'")
        self.fee_model = model
    
    def calculate_cas_to_wcas_fees(self, cas_amount: Decimal, fee_model: str = None) -> Dict[str, Decimal]:
        """
        Calculate fees for CAS -> wCAS bridge operation.
        
        Args:
            cas_amount: Amount of CAS being bridged
            fee_model: Override default fee model ('deducted' or 'direct_payment')
            
        Returns:
            Dict containing fee breakdown and net amounts
        """
        if cas_amount <= 0:
            raise ValueError("Amount must be positive")
        
        model = fee_model or self.fee_model
        
        # Bridge service fee (always deducted from bridge amount)
        bridge_fee = max(cas_amount * self.bridge_fee_percentage, self.min_cas_fee)
        
        # Polygon minting fee estimation
        polygon_fee_matic = Web3.from_wei(self.min_polygon_fee_wei, 'ether')
        polygon_fee_cas_equivalent = self._estimate_polygon_fee_in_cas()
        
        if model == 'direct_payment':
            # User pays MATIC directly, only deduct bridge service fee
            total_deducted_fees = bridge_fee
            net_wcas_amount = cas_amount - bridge_fee
            
            return {
                'input_amount': cas_amount,
                'bridge_fee': bridge_fee,
                'polygon_fee_matic': str(polygon_fee_matic),  # User pays this in MATIC
                'polygon_fee_cas_equivalent': polygon_fee_cas_equivalent,  # For reference
                'total_deducted_fees': total_deducted_fees,
                'matic_fee_required': str(polygon_fee_matic),
                'net_wcas_amount': net_wcas_amount,
                'fee_model': 'direct_payment',
                'fee_percentage': (total_deducted_fees / cas_amount) * 100 if cas_amount > 0 else Decimal('0')
            }
        else:
            # Traditional deducted model
            total_fees = bridge_fee + polygon_fee_cas_equivalent
            max_allowed_fee = cas_amount * self.max_fee_percentage
            if total_fees > max_allowed_fee:
                total_fees = max_allowed_fee
                bridge_fee = max_allowed_fee * Decimal('0.5')
                polygon_fee_cas_equivalent = max_allowed_fee * Decimal('0.5')
            
            net_wcas_amount = cas_amount - total_fees
            
            return {
                'input_amount': cas_amount,
                'bridge_fee': bridge_fee,
                'polygon_network_fee': polygon_fee_cas_equivalent,
                'total_deducted_fees': total_fees,
                'net_wcas_amount': net_wcas_amount,
                'fee_model': 'deducted',
                'fee_percentage': (total_fees / cas_amount) * 100 if cas_amount > 0 else Decimal('0')
            }
    
    def calculate_wcas_to_cas_fees(self, wcas_amount: Decimal, fee_model: str = None) -> Dict[str, Decimal]:
        """
        Calculate fees for wCAS -> CAS bridge operation.
        
        Args:
            wcas_amount: Amount of wCAS being bridged back to CAS
            fee_model: Override default fee model ('deducted' or 'direct_payment')
            
        Returns:
            Dict containing fee breakdown and net amounts
        """
        if wcas_amount <= 0:
            raise ValueError("Amount must be positive")
        
        model = fee_model or self.fee_model
        
        # Bridge service fee
        bridge_fee = max(wcas_amount * self.bridge_fee_percentage, self.min_cas_fee)
        
        # CAS network fee for sending to user
        cas_network_fee = self.min_cas_fee
        
        # Polygon burn fee
        polygon_burn_fee_matic = Web3.from_wei(self.min_polygon_fee_wei * Decimal('0.3'), 'ether')  # Burn costs less
        polygon_burn_fee_cas_equivalent = self._estimate_polygon_burn_fee_in_cas()
        
        if model == 'direct_payment':
            # User pays MATIC for burn transaction, bridge covers CAS network fee
            total_deducted_fees = bridge_fee + cas_network_fee
            net_cas_amount = wcas_amount - total_deducted_fees
            
            return {
                'input_amount': wcas_amount,
                'bridge_fee': bridge_fee,
                'cas_network_fee': cas_network_fee,
                'polygon_burn_fee_matic': str(polygon_burn_fee_matic),  # User pays this in MATIC
                'polygon_burn_fee_cas_equivalent': polygon_burn_fee_cas_equivalent,  # For reference
                'total_deducted_fees': total_deducted_fees,
                'matic_fee_required': str(polygon_burn_fee_matic),
                'net_cas_amount': net_cas_amount,
                'fee_model': 'direct_payment',
                'fee_percentage': (total_deducted_fees / wcas_amount) * 100 if wcas_amount > 0 else Decimal('0')
            }
        else:
            # Traditional deducted model
            total_fees = bridge_fee + cas_network_fee + polygon_burn_fee_cas_equivalent
            max_allowed_fee = wcas_amount * self.max_fee_percentage
            if total_fees > max_allowed_fee:
                total_fees = max_allowed_fee
            
            net_cas_amount = wcas_amount - total_fees
            
            return {
                'input_amount': wcas_amount,
                'bridge_fee': bridge_fee,
                'cas_network_fee': cas_network_fee,
                'polygon_burn_fee': polygon_burn_fee_cas_equivalent,
                'total_deducted_fees': total_fees,
                'net_cas_amount': net_cas_amount,
                'fee_model': 'deducted',
                'fee_percentage': (total_fees / wcas_amount) * 100 if wcas_amount > 0 else Decimal('0')
            }
    
    def _estimate_polygon_fee_in_cas(self) -> Decimal:
        """
        Estimate Polygon network fee in CAS equivalent.
        In production, this would fetch current MATIC/CAS exchange rate.
        """
        # Placeholder: Assume 1 MATIC = 100 CAS (adjust based on actual rates)
        matic_to_cas_rate = Decimal('100')
        estimated_gas_matic = Web3.from_wei(self.min_polygon_fee_wei, 'ether')
        return Decimal(str(estimated_gas_matic)) * matic_to_cas_rate
    
    def _estimate_polygon_burn_fee_in_cas(self) -> Decimal:
        """
        Estimate Polygon burn operation fee in CAS equivalent.
        Burn operations typically cost less gas than minting.
        """
        return self._estimate_polygon_fee_in_cas() * Decimal('0.3')  # 30% of mint fee
    
    def validate_minimum_amount(self, amount: Decimal, operation: str, fee_model: str = None) -> Tuple[bool, Optional[str]]:
        """
        Validate that the bridge amount meets minimum requirements after fees.
        
        Args:
            amount: Amount to be bridged
            operation: 'cas_to_wcas' or 'wcas_to_cas'
            fee_model: Fee model to use for validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if amount <= 0:
            return False, "Amount must be positive"
        
        model = fee_model or self.fee_model
        
        if operation == 'cas_to_wcas':
            fees = self.calculate_cas_to_wcas_fees(amount, model)
            min_required = self.min_cas_fee * 10  # Minimum 10x the base fee
        elif operation == 'wcas_to_cas':
            fees = self.calculate_wcas_to_cas_fees(amount, model)
            min_required = self.min_cas_fee * 10
        else:
            return False, f"Unknown operation: {operation}"
        
        net_amount = fees.get('net_wcas_amount') or fees.get('net_cas_amount', Decimal('0'))
        
        if amount < min_required:
            return False, f"Minimum bridge amount is {min_required}"
        
        if net_amount <= Decimal('0'):
            deducted_fees = fees.get('total_deducted_fees', Decimal('0'))
            return False, f"Amount too small - deducted fees ({deducted_fees}) exceed input amount ({amount})"
        
        # Additional validation for direct payment model
        if model == 'direct_payment':
            matic_required = fees.get('matic_fee_required')
            if matic_required:
                return True, f"Valid. You will need {matic_required} MATIC for network fees."
        
        return True, None
    
    def get_fee_estimate_for_user(self, amount: Decimal, operation: str, fee_model: str = None) -> Dict:
        """
        Get user-friendly fee estimate for display in frontend.
        
        Args:
            amount: Amount to be bridged
            operation: 'cas_to_wcas' or 'wcas_to_cas'
            fee_model: Fee model to use
            
        Returns:
            Dict with fee breakdown for user display
        """
        model = fee_model or self.fee_model
        
        if operation == 'cas_to_wcas':
            fees = self.calculate_cas_to_wcas_fees(amount, model)
            
            if model == 'direct_payment':
                return {
                    'input_amount': str(fees['input_amount']),
                    'bridge_fee': str(fees['bridge_fee']),
                    'matic_fee_required': fees['matic_fee_required'],
                    'output_amount': str(fees['net_wcas_amount']),
                    'fee_percentage': f"{fees['fee_percentage']:.3f}%",
                    'fee_model': 'direct_payment',
                    'fee_breakdown': {
                        'bridge_service_fee': str(fees['bridge_fee']),
                        'polygon_network_fee_matic': fees['matic_fee_required'],
                        'polygon_network_fee_cas_equivalent': str(fees['polygon_fee_cas_equivalent'])
                    },
                    'operation': 'CAS → wCAS',
                    'user_pays_gas': True
                }
            else:
                return {
                    'input_amount': str(fees['input_amount']),
                    'total_fees': str(fees['total_deducted_fees']),
                    'output_amount': str(fees['net_wcas_amount']),
                    'fee_percentage': f"{fees['fee_percentage']:.3f}%",
                    'fee_model': 'deducted',
                    'fee_breakdown': {
                        'bridge_service_fee': str(fees['bridge_fee']),
                        'polygon_network_fee': str(fees['polygon_network_fee'])
                    },
                    'operation': 'CAS → wCAS',
                    'user_pays_gas': False
                }
                
        elif operation == 'wcas_to_cas':
            fees = self.calculate_wcas_to_cas_fees(amount, model)
            
            if model == 'direct_payment':
                return {
                    'input_amount': str(fees['input_amount']),
                    'bridge_fee': str(fees['bridge_fee']),
                    'cas_network_fee': str(fees['cas_network_fee']),
                    'matic_fee_required': fees['matic_fee_required'],
                    'output_amount': str(fees['net_cas_amount']),
                    'fee_percentage': f"{fees['fee_percentage']:.3f}%",
                    'fee_model': 'direct_payment',
                    'fee_breakdown': {
                        'bridge_service_fee': str(fees['bridge_fee']),
                        'cas_network_fee': str(fees['cas_network_fee']),
                        'polygon_burn_fee_matic': fees['matic_fee_required'],
                        'polygon_burn_fee_cas_equivalent': str(fees['polygon_burn_fee_cas_equivalent'])
                    },
                    'operation': 'wCAS → CAS',
                    'user_pays_gas': True
                }
            else:
                return {
                    'input_amount': str(fees['input_amount']),
                    'total_fees': str(fees['total_deducted_fees']),
                    'output_amount': str(fees['net_cas_amount']),
                    'fee_percentage': f"{fees['fee_percentage']:.3f}%",
                    'fee_model': 'deducted',
                    'fee_breakdown': {
                        'bridge_service_fee': str(fees['bridge_fee']),
                        'cas_network_fee': str(fees['cas_network_fee']),
                        'polygon_burn_fee': str(fees['polygon_burn_fee'])
                    },
                    'operation': 'wCAS → CAS',
                    'user_pays_gas': False
                }
        else:
            raise ValueError(f"Unknown operation: {operation}")


# Global instance
fee_service = FeeService() 