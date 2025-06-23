"""
MATIC Fee Service - Allows users to pay Polygon fees using wCAS/CAS tokens.
Handles conversion from wCAS/CAS to MATIC for gas payments.
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple
from web3 import Web3

from backend.config import settings

logger = logging.getLogger(__name__)

class MaticFeeService:
    """Service for handling MATIC fee payments using wCAS/CAS tokens."""
    
    def __init__(self):
        # Exchange rates (in production, fetch from price oracle)
        self.matic_to_cas_rate = Decimal('100')  # 1 MATIC = 100 CAS (example)
        self.wcas_to_matic_rate = Decimal('0.01')  # 1 wCAS = 0.01 MATIC (example)
        
        # Fee conversion settings
        self.conversion_fee_percentage = Decimal('0.005')  # 0.5% conversion fee
        self.min_matic_balance = Web3.to_wei(0.001, 'ether')  # Minimum MATIC to maintain
        
        # Gas price buffers
        self.gas_price_buffer = Decimal('1.2')  # 20% buffer for gas price fluctuations
    
    def calculate_matic_fee_in_tokens(self, gas_estimate: int, token_type: str, gas_price_wei: int = None) -> Dict:
        """
        Calculate how much wCAS/CAS is needed to cover MATIC fees.
        
        Args:
            gas_estimate: Estimated gas units needed
            token_type: 'wCAS' or 'CAS'
            gas_price_wei: Gas price in wei (if None, will estimate)
            
        Returns:
            Dict with conversion details
        """
        # Estimate gas price if not provided
        if gas_price_wei is None:
            gas_price_wei = Web3.to_wei(30, 'gwei')  # Default 30 gwei
        
        # Calculate total MATIC needed (with buffer)
        matic_needed_wei = int(gas_estimate * gas_price_wei * self.gas_price_buffer)
        matic_needed = Web3.from_wei(matic_needed_wei, 'ether')
        
        # Convert to token amount
        if token_type.upper() == 'WCAS':
            tokens_needed = Decimal(str(matic_needed)) / self.wcas_to_matic_rate
            conversion_fee = tokens_needed * self.conversion_fee_percentage
        elif token_type.upper() == 'CAS':
            tokens_needed = Decimal(str(matic_needed)) * self.matic_to_cas_rate
            conversion_fee = tokens_needed * self.conversion_fee_percentage
        else:
            raise ValueError("Token type must be 'wCAS' or 'CAS'")
        
        total_tokens_needed = tokens_needed + conversion_fee
        
        return {
            'gas_estimate': gas_estimate,
            'gas_price_gwei': Web3.from_wei(gas_price_wei, 'gwei'),
            'matic_needed': str(matic_needed),
            'matic_needed_wei': str(matic_needed_wei),
            'token_type': token_type.upper(),
            'tokens_for_gas': str(tokens_needed),
            'conversion_fee': str(conversion_fee),
            'total_tokens_needed': str(total_tokens_needed),
            'conversion_rate': str(self.wcas_to_matic_rate if token_type.upper() == 'WCAS' else self.matic_to_cas_rate),
            'conversion_fee_percentage': str(self.conversion_fee_percentage * 100)
        }
    
    def estimate_bridge_transaction_costs(self, operation: str, token_payment: str = 'MATIC') -> Dict:
        """
        Estimate transaction costs for different bridge operations.
        
        Args:
            operation: 'mint_wcas' or 'burn_wcas'
            token_payment: 'MATIC', 'wCAS', or 'CAS'
            
        Returns:
            Dict with cost estimates
        """
        # Gas estimates for different operations
        gas_estimates = {
            'mint_wcas': 165000,  # Mint + possible forwarding transfer
            'burn_wcas': 80000,   # ERC20 burn operation
            'transfer_wcas': 65000,  # ERC20 transfer
            'approve_wcas': 50000    # ERC20 approval
        }
        
        base_gas = gas_estimates.get(operation, 100000)
        
        if token_payment == 'MATIC':
            # Standard MATIC payment
            gas_price_wei = Web3.to_wei(30, 'gwei')
            matic_cost = Web3.from_wei(base_gas * gas_price_wei, 'ether')
            
            return {
                'operation': operation,
                'payment_method': 'MATIC',
                'gas_estimate': base_gas,
                'matic_cost': str(matic_cost),
                'user_pays_directly': True
            }
        else:
            # Token-based payment
            return self.calculate_matic_fee_in_tokens(base_gas, token_payment)
    
    def create_fee_payment_transaction(self, user_address: str, token_amount: Decimal, token_type: str) -> Dict:
        """
        Create a transaction for converting tokens to MATIC for fees.
        
        Args:
            user_address: User's address
            token_amount: Amount of tokens to convert
            token_type: 'wCAS' or 'CAS'
            
        Returns:
            Transaction details
        """
        # This would integrate with a DEX or conversion service
        # For now, return a mock transaction structure
        
        if token_type.upper() == 'WCAS':
            matic_received = token_amount * self.wcas_to_matic_rate
        else:  # CAS
            matic_received = token_amount / self.matic_to_cas_rate
        
        conversion_fee = token_amount * self.conversion_fee_percentage
        net_matic = matic_received * (1 - self.conversion_fee_percentage)
        
        return {
            'user_address': user_address,
            'input_token': token_type.upper(),
            'input_amount': str(token_amount),
            'conversion_fee': str(conversion_fee),
            'matic_received': str(net_matic),
            'transaction_type': 'token_to_matic_conversion',
            'status': 'pending',
            'estimated_gas': 150000  # For the conversion transaction itself
        }
    
    def get_user_fee_options(self, user_address: str, operation: str) -> Dict:
        """
        Get available fee payment options for a user.
        
        Args:
            user_address: User's address
            operation: Bridge operation type
            
        Returns:
            Available payment options
        """
        costs = self.estimate_bridge_transaction_costs(operation)
        
        options = {
            'operation': operation,
            'user_address': user_address,
            'payment_options': []
        }
        
        # Option 1: Direct MATIC payment
        options['payment_options'].append({
            'method': 'direct_matic',
            'display_name': 'Pay with MATIC',
            'matic_required': costs.get('matic_cost', '0.001'),
            'description': 'Pay gas fees directly with MATIC tokens'
        })
        
        # Option 2: wCAS conversion
        wcas_costs = self.calculate_matic_fee_in_tokens(costs.get('gas_estimate', 100000), 'wCAS')
        options['payment_options'].append({
            'method': 'wcas_conversion',
            'display_name': 'Pay with wCAS',
            'wcas_required': wcas_costs['total_tokens_needed'],
            'matic_equivalent': wcas_costs['matic_needed'],
            'conversion_fee': wcas_costs['conversion_fee'],
            'description': f'Convert wCAS to MATIC (includes {wcas_costs["conversion_fee_percentage"]}% conversion fee)'
        })
        
        # Option 3: CAS conversion (if applicable)
        cas_costs = self.calculate_matic_fee_in_tokens(costs.get('gas_estimate', 100000), 'CAS')
        options['payment_options'].append({
            'method': 'cas_conversion',
            'display_name': 'Pay with CAS',
            'cas_required': cas_costs['total_tokens_needed'],
            'matic_equivalent': cas_costs['matic_needed'],
            'conversion_fee': cas_costs['conversion_fee'],
            'description': f'Convert CAS to MATIC (includes {cas_costs["conversion_fee_percentage"]}% conversion fee)'
        })
        
        return options
    
    def update_exchange_rates(self, matic_to_cas: Decimal = None, wcas_to_matic: Decimal = None):
        """
        Update exchange rates from external price feeds.
        
        Args:
            matic_to_cas: New MATIC to CAS rate
            wcas_to_matic: New wCAS to MATIC rate
        """
        if matic_to_cas:
            self.matic_to_cas_rate = matic_to_cas
            logger.info(f"Updated MATIC/CAS rate to {matic_to_cas}")
        
        if wcas_to_matic:
            self.wcas_to_matic_rate = wcas_to_matic
            logger.info(f"Updated wCAS/MATIC rate to {wcas_to_matic}")


# Global instance
matic_fee_service = MaticFeeService() 