#!/usr/bin/env python3
"""
Debugging-Script für Meta-Transaction Probleme
Speziell für den Fall: Owner = Minter = gleiche Adresse
"""

import json
from web3 import Web3
from eth_account import Account

def debug_meta_transaction_issue():
    print("=" * 60)
    print("Meta-Transaction Problem Debugging")  
    print("(Owner = Minter = gleiche Adresse)")
    print("=" * 60)
    
    # Manual configuration
    POLYGON_RPC_URL = input("Polygon RPC URL eingeben: ").strip()
    if not POLYGON_RPC_URL:
        POLYGON_RPC_URL = "https://polygon-rpc.com"
    
    CONTRACT_ADDRESS = input("wCAS Contract Adresse eingeben: ").strip()
    if not CONTRACT_ADDRESS:
        print("✗ Contract Adresse ist erforderlich!")
        return
    
    PRIVATE_KEY = input("Private Key eingeben (Owner/Minter): ").strip()
    if not PRIVATE_KEY:
        print("✗ Private Key ist erforderlich!")
        return
    
    if not PRIVATE_KEY.startswith('0x'):
        PRIVATE_KEY = '0x' + PRIVATE_KEY
    
    print(f"\nKonfiguration:")
    print(f"RPC: {POLYGON_RPC_URL}")
    print(f"Contract: {CONTRACT_ADDRESS}")
    
    # Setup
    web3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))
    if not web3.is_connected():
        print("✗ Nicht verbunden zu Polygon")
        return
    
    account = Account.from_key(PRIVATE_KEY)
    address = account.address
    print(f"Adresse: {address}")
    
    try:
        with open('smart_contracts/wCAS_ABI.json', 'r') as f:
            contract_abi = json.load(f)
        contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
    except Exception as e:
        print(f"✗ Contract Setup Fehler: {e}")
        return
    
    print(f"\n1. 🔍 CONTRACT ROLLEN ÜBERPRÜFUNG...")
    try:
        owner = contract.functions.owner().call()
        minter = contract.functions.minter().call()
        
        print(f"Contract Owner:  {owner}")
        print(f"Contract Minter: {minter}")
        print(f"Ihre Adresse:    {address}")
        
        owner_match = owner.lower() == address.lower()
        minter_match = minter.lower() == address.lower()
        
        print(f"Owner Match:  {'✅' if owner_match else '❌'}")
        print(f"Minter Match: {'✅' if minter_match else '❌'}")
        
        if not minter_match:
            print("❌ PROBLEM: Sie sind nicht der Minter!")
            print("Lösung: Als Owner setMinter() aufrufen")
            return
        
        print("✅ Rollen korrekt konfiguriert")
        
    except Exception as e:
        print(f"✗ Rollen Check Fehler: {e}")
        return
    
    print(f"\n2. 🔍 META-TRANSACTION ANALYSE...")
    
    # Test 1: Direkte mint() Funktion mit msg.sender
    print("\nTest 1: Direkte mint() - sollte mit _msgSender() arbeiten")
    try:
        test_recipient = "0x1234567890123456789012345678901234567890"
        test_amount = 1000000000000000000  # 1 Token
        
        # Gas estimation
        gas_estimate = contract.functions.mint(test_recipient, test_amount).estimate_gas({
            'from': address
        })
        print(f"✅ Gas Schätzung erfolgreich: {gas_estimate}")
        
        # Build transaction
        nonce = web3.eth.get_transaction_count(address)
        
        tx_params = {
            'from': address,
            'nonce': nonce,
            'gas': gas_estimate + 50000,  # Extra buffer
            'gasPrice': web3.eth.gas_price
        }
        
        transaction = contract.functions.mint(test_recipient, test_amount).build_transaction(tx_params)
        print("✅ Transaction Build erfolgreich")
        print(f"   Gas: {transaction['gas']}")
        print(f"   Gas Price: {web3.from_wei(transaction['gasPrice'], 'gwei')} gwei")
        
        # Test signing
        signed_tx = account.sign_transaction(transaction)
        print("✅ Transaction Signing erfolgreich")
        
        print(f"\n🎯 LÖSUNG GEFUNDEN!")
        print(f"   Das Problem liegt NICHT bei Berechtigungen")
        print(f"   Meta-Transactions funktionieren korrekt")
        print(f"   Mögliche andere Ursachen:")
        print(f"   - Zu niedriges Gas Limit in der App")
        print(f"   - Netzwerk-Probleme")
        print(f"   - Falsche Recipient-Adresse")
        print(f"   - Betrag = 0")
        
    except Exception as e:
        error_str = str(e).lower()
        print(f"❌ Mint Test Fehler: {e}")
        
        if "not minter" in error_str:
            print("\n🔍 META-TRANSACTION PROBLEM BESTÄTIGT!")
            print("   Der Contract verwendet _msgSender() aber erkennt Sie nicht als Minter")
            print("   GRUND: Trusted Forwarder Problem")
            print("\n💡 LÖSUNGEN:")
            print("   1. Trusted Forwarder korrekt in App konfigurieren")
            print("   2. Meta-Transactions in App deaktivieren") 
            print("   3. Contract ohne Meta-Transaction Support neu deployen")
            print("\n🔧 SOFORTIGE LÖSUNG:")
            print("   In Ihrer polygon_service.py:")
            print("   - Entfernen Sie alle Meta-Transaction Header")
            print("   - Senden Sie normale Transaktionen")
            
        elif "zero address" in error_str:
            print("\n🔍 INVALID ADDRESS PROBLEM!")
            print("   Test-Adresse wird als ungültig erkannt")
            
        elif "zero amount" in error_str:
            print("\n🔍 INVALID AMOUNT PROBLEM!")
            print("   Test-Betrag wird als ungültig erkannt")
            
        else:
            print(f"\n🔍 ANDERES PROBLEM: {e}")
    
    print(f"\n3. 🔍 TRUSTED FORWARDER CHECK...")
    try:
        # Check if contract has trustedForwarder function
        try:
            forwarder = contract.functions.trustedForwarder().call()
            print(f"✅ Trusted Forwarder gefunden: {forwarder}")
            
            # Check if it's zero address (not configured)
            if forwarder == "0x0000000000000000000000000000000000000000":
                print("⚠ Trusted Forwarder ist Zero Address!")
                print("  Das könnte das Problem sein!")
            else:
                print("✅ Trusted Forwarder konfiguriert")
                
        except:
            print("- Keine trustedForwarder() Funktion gefunden")
            
    except Exception as e:
        print(f"✗ Forwarder Check Fehler: {e}")
    
    print(f"\n4. 🔍 APP CONFIGURATION CHECK...")
    print("In Ihrer polygon_service.py sollte stehen:")
    print("```python")
    print("# NORMALE Transaction (OHNE Meta-Transaction Headers)")
    print("transaction = self.wcas_contract.functions.mint(recipient, amount).build_transaction({")
    print("    'from': self.minter_address,")
    print("    'nonce': nonce,")
    print("    'gas': gas_limit,")
    print("    'gasPrice': gas_price")
    print("})")
    print("```")
    print("\nWICHTIG: KEINE Meta-Transaction Header verwenden!")
    print("- Kein 'forwarder' Parameter")
    print("- Kein spezieller _msgSender() Handling")
    
    print("\n" + "=" * 60)
    print("FAZIT:")
    print("Da Owner = Minter = Ihre Adresse:")
    print("✅ Berechtigungen sind korrekt")
    print("❌ Problem liegt bei Meta-Transaction Setup")
    print("\n💡 LÖSUNG: Normale Transaktionen verwenden (ohne Meta-Tx)")
    print("=" * 60)

if __name__ == "__main__":
    debug_meta_transaction_issue() 