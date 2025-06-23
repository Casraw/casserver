#!/usr/bin/env python3
"""
Debugging script for wCAS minting issues
Checks contract state and minter permissions
"""

import os
import sys
import json
from web3 import Web3
from eth_account import Account

# Add backend to path
sys.path.append('backend')
from config import settings

def debug_minting_issue():
    """Comprehensive debugging of minting permissions and contract state"""
    
    print("=" * 60)
    print("wCAS Minting Issue Debugging")
    print("=" * 60)
    
    # 1. Check Web3 connection
    print("\n1. Checking Web3 Connection...")
    try:
        web3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
        if web3.is_connected():
            print(f"✓ Connected to Polygon RPC: {settings.POLYGON_RPC_URL}")
            print(f"✓ Chain ID: {web3.eth.chain_id}")
            print(f"✓ Current block: {web3.eth.block_number}")
        else:
            print("✗ NOT CONNECTED to Polygon RPC")
            return
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return
    
    # 2. Check contract ABI and address
    print("\n2. Checking Contract Configuration...")
    try:
        with open('smart_contracts/wCAS_ABI.json', 'r') as f:
            contract_abi = json.load(f)
        print(f"✓ Contract ABI loaded ({len(contract_abi)} functions)")
        
        contract_address = settings.WCAS_CONTRACT_ADDRESS
        print(f"✓ Contract Address: {contract_address}")
        
        # Check if contract exists
        code = web3.eth.get_code(contract_address)
        if code.hex() == '0x':
            print("✗ Contract not deployed at this address!")
            return
        else:
            print(f"✓ Contract deployed (code length: {len(code)} bytes)")
        
        # Create contract instance
        contract = web3.eth.contract(address=contract_address, abi=contract_abi)
        
    except Exception as e:
        print(f"✗ Contract setup error: {e}")
        return
    
    # 3. Check minter account setup
    print("\n3. Checking Minter Account Setup...")
    try:
        minter_private_key = settings.MINTER_PRIVATE_KEY
        if not minter_private_key or minter_private_key == "placeholder":
            print("✗ MINTER_PRIVATE_KEY not set or is placeholder")
            return
        
        minter_account = Account.from_key(minter_private_key)
        minter_address = minter_account.address
        print(f"✓ Minter address from private key: {minter_address}")
        
        # Check minter balance
        balance = web3.eth.get_balance(minter_address)
        balance_matic = web3.from_wei(balance, 'ether')
        print(f"✓ Minter MATIC balance: {balance_matic}")
        
        if balance_matic < 0.001:
            print("⚠ WARNING: Minter has very low MATIC balance")
        
    except Exception as e:
        print(f"✗ Minter account error: {e}")
        return
    
    # 4. Check contract state
    print("\n4. Checking Contract State...")
    try:
        # Get contract owner
        owner = contract.functions.owner().call()
        print(f"✓ Contract Owner: {owner}")
        
        # Get contract minter
        contract_minter = contract.functions.minter().call()
        print(f"✓ Contract Minter: {contract_minter}")
        
        # Get relayer (if exists)
        try:
            relayer = contract.functions.relayer().call()
            print(f"✓ Contract Relayer: {relayer}")
        except:
            print("- No relayer function found")
        
        # Check minter permission
        if contract_minter.lower() == minter_address.lower():
            print("✓ MINTER PERMISSION: CORRECT")
        else:
            print("✗ MINTER PERMISSION: INCORRECT")
            print(f"  Contract expects: {contract_minter}")
            print(f"  Our minter is:   {minter_address}")
            print("  SOLUTION: Update contract minter or use correct private key")
        
    except Exception as e:
        print(f"✗ Contract state error: {e}")
        return
    
    # 5. Test mint function call (read-only)
    print("\n5. Testing Mint Function Call...")
    try:
        test_recipient = "0x1234567890123456789012345678901234567890"
        test_amount = 1000000000000000000  # 1 token with 18 decimals
        
        # Try to build transaction
        nonce = web3.eth.get_transaction_count(minter_address)
        
        tx_params = {
            'from': minter_address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': web3.eth.gas_price
        }
        
        # Build transaction
        transaction = contract.functions.mint(test_recipient, test_amount).build_transaction(tx_params)
        print("✓ Mint transaction built successfully")
        print(f"  Gas estimate: {transaction['gas']}")
        print(f"  Gas price: {web3.from_wei(transaction['gasPrice'], 'gwei')} gwei")
        
        # Check if we can estimate gas
        gas_estimate = contract.functions.mint(test_recipient, test_amount).estimate_gas({'from': minter_address})
        print(f"✓ Gas estimate: {gas_estimate}")
        
    except Exception as e:
        print(f"✗ Mint function test error: {e}")
        if "not minter" in str(e).lower():
            print("  CONFIRMED: Minter permission issue")
        elif "zero address" in str(e).lower():
            print("  CONFIRMED: Invalid address issue")
        elif "zero amount" in str(e).lower():
            print("  CONFIRMED: Invalid amount issue")
        return
    
    # 6. Check trusted forwarder (if meta-transactions are used)
    print("\n6. Checking Meta-Transaction Setup...")
    try:
        # Check if contract has trusted forwarder
        forwarder_code = contract.contract_address  # This should be checked differently
        print("- Meta-transaction check not implemented yet")
        
    except Exception as e:
        print(f"- Meta-transaction check error: {e}")
    
    print("\n" + "=" * 60)
    print("DEBUGGING COMPLETE")
    print("=" * 60)
    
    # Summary
    print("\nSUMMARY:")
    if contract_minter.lower() == minter_address.lower():
        print("✓ Minter permissions appear correct")
        print("  If minting still fails, check:")
        print("  - Gas limit (try increasing to 200000)")
        print("  - Recipient address validity")
        print("  - Amount > 0")
        print("  - MATIC balance for gas fees")
    else:
        print("✗ MINTER PERMISSION ISSUE FOUND")
        print("  TO FIX:")
        print(f"  Option 1: Update contract minter to: {minter_address}")
        print(f"  Option 2: Use private key for address: {contract_minter}")

if __name__ == "__main__":
    debug_minting_issue() 