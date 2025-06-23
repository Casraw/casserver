#!/usr/bin/env python3
"""
Einfaches Debugging-Script um das wCAS Minting Problem zu diagnostizieren
Basiert auf manueller Eingabe der wichtigsten Parameter
"""

import json
from web3 import Web3
from eth_account import Account

def debug_minting_manual():
    print("=" * 60)
    print("wCAS Minting Issue Debugging (Manuell)")
    print("=" * 60)
    
    # Manual configuration - you need to fill these in
    POLYGON_RPC_URL = input("Polygon RPC URL eingeben (z.B. https://polygon-rpc.com): ").strip()
    if not POLYGON_RPC_URL:
        POLYGON_RPC_URL = "https://polygon-rpc.com"
    
    CONTRACT_ADDRESS = input("wCAS Contract Adresse eingeben: ").strip()
    if not CONTRACT_ADDRESS:
        print("✗ Contract Adresse ist erforderlich!")
        return
    
    MINTER_PRIVATE_KEY = input("Minter Private Key eingeben (ohne 0x): ").strip()
    if not MINTER_PRIVATE_KEY:
        print("✗ Minter Private Key ist erforderlich!")
        return
    
    # Add 0x prefix if missing
    if not MINTER_PRIVATE_KEY.startswith('0x'):
        MINTER_PRIVATE_KEY = '0x' + MINTER_PRIVATE_KEY
    
    print(f"\nVerwende:")
    print(f"RPC: {POLYGON_RPC_URL}")
    print(f"Contract: {CONTRACT_ADDRESS}")
    print(f"Private Key: {'0x' + '*' * (len(MINTER_PRIVATE_KEY) - 10) + MINTER_PRIVATE_KEY[-8:]}")
    
    # 1. Check Web3 connection
    print("\n1. Prüfe Web3 Verbindung...")
    try:
        web3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))
        if web3.is_connected():
            print(f"✓ Verbunden zu Polygon")
            print(f"✓ Chain ID: {web3.eth.chain_id}")
            print(f"✓ Aktueller Block: {web3.eth.block_number}")
        else:
            print("✗ NICHT VERBUNDEN zu Polygon RPC")
            return
    except Exception as e:
        print(f"✗ Verbindungsfehler: {e}")
        return
    
    # 2. Check minter account
    print("\n2. Prüfe Minter Account...")
    try:
        minter_account = Account.from_key(MINTER_PRIVATE_KEY)
        minter_address = minter_account.address
        print(f"✓ Minter Adresse: {minter_address}")
        
        # Check balance
        balance = web3.eth.get_balance(minter_address)
        balance_matic = web3.from_wei(balance, 'ether')
        print(f"✓ Minter MATIC Balance: {balance_matic}")
        
        if balance_matic < 0.001:
            print("⚠ WARNUNG: Sehr niedrige MATIC Balance!")
        
    except Exception as e:
        print(f"✗ Minter Account Fehler: {e}")
        return
    
    # 3. Load contract ABI and check contract
    print("\n3. Lade Contract ABI...")
    try:
        with open('smart_contracts/wCAS_ABI.json', 'r') as f:
            contract_abi = json.load(f)
        print(f"✓ Contract ABI geladen ({len(contract_abi)} Funktionen)")
        
        # Check if contract exists
        code = web3.eth.get_code(CONTRACT_ADDRESS)
        if code.hex() == '0x':
            print("✗ Contract nicht deployed an dieser Adresse!")
            return
        else:
            print(f"✓ Contract deployed (Code Länge: {len(code)} bytes)")
        
        # Create contract instance
        contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
        
    except FileNotFoundError:
        print("✗ wCAS_ABI.json nicht gefunden!")
        return
    except Exception as e:
        print(f"✗ Contract Setup Fehler: {e}")
        return
    
    # 4. Check contract roles
    print("\n4. Prüfe Contract Rollen...")
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
            print("- Keine Relayer Funktion gefunden")
        
        # CRITICAL CHECK: Minter permission
        print(f"\n🔍 KRITISCHER CHECK:")
        print(f"Contract erwartet Minter: {contract_minter}")
        print(f"Unser Minter ist:       {minter_address}")
        
        if contract_minter.lower() == minter_address.lower():
            print("✅ MINTER BERECHTIGUNG: KORREKT")
        else:
            print("❌ MINTER BERECHTIGUNG: FALSCH!")
            print("\n🔧 LÖSUNGEN:")
            print(f"Option 1: Contract Minter setzen auf: {minter_address}")
            print(f"         Contract Owner ({owner}) muss setMinter() aufrufen")
            print(f"Option 2: Private Key verwenden für: {contract_minter}")
            return False
        
    except Exception as e:
        print(f"✗ Contract Rollen Fehler: {e}")
        return
    
    # 5. Test mint function
    print("\n5. Teste Mint Funktion...")
    try:
        test_recipient = "0x1234567890123456789012345678901234567890"
        test_amount = 1000000000000000000  # 1 token with 18 decimals
        
        # Try to estimate gas
        gas_estimate = contract.functions.mint(test_recipient, test_amount).estimate_gas({'from': minter_address})
        print(f"✓ Gas Schätzung erfolgreich: {gas_estimate}")
        
        # Try to build transaction
        nonce = web3.eth.get_transaction_count(minter_address)
        
        tx_params = {
            'from': minter_address,
            'nonce': nonce,
            'gas': min(gas_estimate + 20000, 200000),  # Add buffer
            'gasPrice': web3.eth.gas_price
        }
        
        transaction = contract.functions.mint(test_recipient, test_amount).build_transaction(tx_params)
        print("✓ Mint Transaction erfolgreich gebaut")
        print(f"  Gas: {transaction['gas']}")
        print(f"  Gas Preis: {web3.from_wei(transaction['gasPrice'], 'gwei')} gwei")
        
        print("\n✅ MINTING SOLLTE FUNKTIONIEREN!")
        
    except Exception as e:
        print(f"❌ Mint Funktions Test Fehler: {e}")
        error_str = str(e).lower()
        if "not minter" in error_str:
            print("  🔍 BESTÄTIGT: Minter Berechtigungs Problem")
        elif "zero address" in error_str:
            print("  🔍 BESTÄTIGT: Ungültige Adress Problem")
        elif "zero amount" in error_str:
            print("  🔍 BESTÄTIGT: Ungültiger Betrag Problem")
        else:
            print(f"  🔍 Anderer Fehler: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("DEBUGGING ABGESCHLOSSEN")
    print("=" * 60)
    return True

if __name__ == "__main__":
    debug_minting_manual() 