"""
Integration tests for the fee system.
Tests the actual fee services and API endpoints.
"""

import unittest
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.services.fee_service import fee_service
from backend.services.matic_fee_service import matic_fee_service
from backend.api.fee_routes import router
from fastapi import FastAPI

class TestFeeSystemIntegration(unittest.TestCase):
    """Integration tests for the fee system."""
    
    def setUp(self):
        """Set up test client."""
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
    
    def test_fee_service_basic_functionality(self):
        """Test basic fee service functionality."""
        # Test CAS to wCAS fees
        amount = Decimal('100.0')
        fees = fee_service.calculate_cas_to_wcas_fees(amount, 'direct_payment')
        
        self.assertIn('input_amount', fees)
        self.assertIn('bridge_fee', fees)
        self.assertIn('net_wcas_amount', fees)
        self.assertEqual(fees['input_amount'], amount)
        self.assertEqual(fees['fee_model'], 'direct_payment')
        
        # Test wCAS to CAS fees
        fees = fee_service.calculate_wcas_to_cas_fees(amount, 'deducted')
        
        self.assertIn('input_amount', fees)
        self.assertIn('total_deducted_fees', fees)
        self.assertIn('net_cas_amount', fees)
        self.assertEqual(fees['fee_model'], 'deducted')
    
    def test_fee_service_validation(self):
        """Test fee service validation."""
        # Test minimum amount validation
        small_amount = Decimal('0.001')
        is_valid, error = fee_service.validate_minimum_amount(small_amount, 'cas_to_wcas')
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        
        # Test valid amount
        valid_amount = Decimal('10.0')
        is_valid, error = fee_service.validate_minimum_amount(valid_amount, 'cas_to_wcas')
        self.assertTrue(is_valid)
    
    def test_fee_service_user_estimate(self):
        """Test user-friendly fee estimates."""
        amount = Decimal('50.0')
        estimate = fee_service.get_fee_estimate_for_user(amount, 'cas_to_wcas', 'direct_payment')
        
        self.assertIn('input_amount', estimate)
        self.assertIn('output_amount', estimate)
        self.assertIn('fee_breakdown', estimate)
        self.assertIn('operation', estimate)
        self.assertEqual(estimate['fee_model'], 'direct_payment')
    
    def test_matic_fee_service_basic_functionality(self):
        """Test basic MATIC fee service functionality."""
        # Test MATIC fee calculation in tokens
        gas_estimate = 100000
        wcas_fees = matic_fee_service.calculate_matic_fee_in_tokens(gas_estimate, 'wCAS')
        
        self.assertIn('gas_estimate', wcas_fees)
        self.assertIn('matic_needed', wcas_fees)
        self.assertIn('total_tokens_needed', wcas_fees)
        self.assertEqual(wcas_fees['token_type'], 'WCAS')
        
        # Test with CAS
        cas_fees = matic_fee_service.calculate_matic_fee_in_tokens(gas_estimate, 'CAS')
        self.assertEqual(cas_fees['token_type'], 'CAS')
    
    def test_matic_fee_service_bridge_costs(self):
        """Test bridge transaction cost estimation."""
        # Test mint operation
        mint_costs = matic_fee_service.estimate_bridge_transaction_costs('mint_wcas', 'MATIC')
        
        self.assertIn('operation', mint_costs)
        self.assertIn('payment_method', mint_costs)
        self.assertIn('gas_estimate', mint_costs)
        self.assertEqual(mint_costs['operation'], 'mint_wcas')
        
        # Test with token payment
        token_costs = matic_fee_service.estimate_bridge_transaction_costs('burn_wcas', 'wCAS')
        self.assertIn('total_tokens_needed', token_costs)
    
    def test_matic_fee_service_user_options(self):
        """Test user fee options."""
        user_address = "0x1234567890123456789012345678901234567890"
        options = matic_fee_service.get_user_fee_options(user_address, 'mint_wcas')
        
        self.assertIn('operation', options)
        self.assertIn('user_address', options)
        self.assertIn('payment_options', options)
        self.assertEqual(options['user_address'], user_address)
        
        # Should have multiple payment options
        payment_options = options['payment_options']
        self.assertGreater(len(payment_options), 1)
        
        # Check for expected payment methods
        methods = [opt['method'] for opt in payment_options]
        self.assertIn('direct_matic', methods)
        self.assertIn('wcas_conversion', methods)
    
    def test_fee_api_estimate_endpoint(self):
        """Test the fee estimation API endpoint."""
        response = self.client.post("/api/fees/estimate", json={
            "amount": "100.0",
            "operation": "cas_to_wcas",
            "fee_model": "direct_payment"
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('input_amount', data)
        self.assertIn('output_amount', data)
        self.assertIn('fee_breakdown', data)
        self.assertIn('is_valid', data)
    
    def test_fee_api_quick_estimate_endpoint(self):
        """Test the quick fee estimation endpoint."""
        response = self.client.get("/api/fees/quick-estimate", params={
            "amount": "50.0",
            "operation": "wcas_to_cas",
            "fee_model": "deducted"
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('input_amount', data)
        self.assertIn('output_amount', data)
        self.assertIn('total_fees', data)
        self.assertIn('is_valid', data)
    
    def test_fee_api_config_endpoint(self):
        """Test the fee configuration endpoint."""
        response = self.client.get("/api/fees/config")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('bridge_fee_percentage', data)
        self.assertIn('fee_models', data)
        self.assertIn('default_fee_model', data)
    
    def test_fee_api_matic_options_endpoint(self):
        """Test the MATIC options endpoint."""
        user_address = "0x1234567890123456789012345678901234567890"
        response = self.client.get(f"/api/fees/matic-options/{user_address}", params={
            "operation": "mint_wcas"
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('operation', data)
        self.assertIn('payment_options', data)
    
    def test_fee_api_error_handling(self):
        """Test API error handling."""
        # Test invalid amount
        response = self.client.post("/api/fees/estimate", json={
            "amount": "-10.0",
            "operation": "cas_to_wcas"
        })
        self.assertEqual(response.status_code, 400)
        
        # Test invalid operation
        response = self.client.post("/api/fees/estimate", json={
            "amount": "100.0",
            "operation": "invalid_operation"
        })
        self.assertEqual(response.status_code, 400)
    
    def test_fee_models_consistency(self):
        """Test that both fee models work consistently."""
        amount = Decimal('100.0')
        
        # Test direct payment model
        direct_fees = fee_service.get_fee_estimate_for_user(amount, 'cas_to_wcas', 'direct_payment')
        self.assertEqual(direct_fees['fee_model'], 'direct_payment')
        self.assertIn('matic_fee_required', direct_fees)
        
        # Test deducted model
        deducted_fees = fee_service.get_fee_estimate_for_user(amount, 'cas_to_wcas', 'deducted')
        self.assertEqual(deducted_fees['fee_model'], 'deducted')
        self.assertIn('total_fees', deducted_fees)
        
        # Direct payment should result in higher output amount (less fees deducted)
        direct_output = Decimal(direct_fees['output_amount'])
        deducted_output = Decimal(deducted_fees['output_amount'])
        self.assertGreater(direct_output, deducted_output)

if __name__ == '__main__':
    unittest.main() 