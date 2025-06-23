#!/usr/bin/env python3
"""
Check für häufige wCAS Smart Contract Minting-Probleme
Analysiert den Contract Code und identifiziert potenzielle Probleme
"""

def analyze_contract_issues():
    print("=" * 60)
    print("wCAS Smart Contract Problem-Analyse")
    print("=" * 60)
    
    print("\n📋 HÄUFIGE MINTING-PROBLEME UND LÖSUNGEN:\n")
    
    print("1. 🔑 MINTER PERMISSION PROBLEM (häufigste Ursache)")
    print("   Fehler: 'wCAS: not minter'")
    print("   Ursache: Minter-Adresse im Contract ≠ verwendete Adresse")
    print("   Lösung:")
    print("   - Contract Owner ruft setMinter(neue_adresse) auf")
    print("   - ODER verwende private key der bereits gesetzten Minter-Adresse")
    print()
    
    print("2. ⚡ META-TRANSACTION PROBLEM")
    print("   Fehler: 'wCAS: not minter' obwohl Adresse korrekt")
    print("   Ursache: Contract verwendet _msgSender() statt msg.sender")
    print("   Lösung:")
    print("   - Trusted Forwarder korrekt konfigurieren")
    print("   - ODER Meta-Tx System deaktivieren im Contract")
    print()
    
    print("3. 💰 INVALID ADDRESS/AMOUNT")
    print("   Fehler: 'wCAS: zero address' oder 'wCAS: zero amount'")
    print("   Ursache: Validierung schlägt fehl")
    print("   Lösung:")
    print("   - Zieladresse ≠ 0x0000...0000")
    print("   - Betrag > 0")
    print()
    
    print("4. ⛽ GAS LIMIT PROBLEM")
    print("   Fehler: Out of gas oder Transaction reverted")
    print("   Ursache: Zu niedriges Gas Limit")
    print("   Lösung:")
    print("   - Gas Limit erhöhen (empfohlen: 150,000-200,000)")
    print()
    
    print("5. 🚫 CONTRACT PAUSED/FROZEN")
    print("   Fehler: Transaction reverted ohne spezifischen Grund")
    print("   Ursache: Contract Owner hat Funktionen gesperrt")
    print("   Lösung:")
    print("   - Owner muss Contract entsperren")
    print()
    
    print("\n🔧 DEBUGGING-SCHRITTE:")
    print("1. Führe 'python simple_mint_debug.py' aus")
    print("2. Überprüfe Minter-Berechtigung im Contract")
    print("3. Teste mit höherem Gas Limit")
    print("4. Überprüfe Trusted Forwarder Setup")
    print("5. Kontaktiere Contract Owner wenn nötig")
    print()
    
    print("\n📚 SMART CONTRACT ANALYSE:")
    
    # Analyse des aktuellen Contracts
    try:
        with open('smart_contracts/wCAS.sol', 'r') as f:
            contract_code = f.read()
        
        print("\n✓ Smart Contract gefunden. Analyse:")
        
        # Check for meta-transaction support
        if 'ERC2771Context' in contract_code:
            print("⚠ Meta-Transaction Support AKTIVIERT")
            print("  - Contract verwendet _msgSender() statt msg.sender")
            print("  - Trusted Forwarder muss korrekt konfiguriert sein")
            print("  - Problem könnte bei Meta-Tx Setup liegen")
        else:
            print("✓ Keine Meta-Transactions (verwendet msg.sender)")
        
        # Check for access control
        if 'onlyMinter' in contract_code:
            print("✓ Minter Access Control vorhanden")
            
        if 'validAddress' in contract_code:
            print("✓ Address Validation vorhanden")
            
        if 'validAmount' in contract_code:
            print("✓ Amount Validation vorhanden")
            
        # Check for owner functions
        if 'setMinter' in contract_code:
            print("✓ setMinter() Funktion vorhanden")
            print("  - Owner kann Minter-Adresse ändern")
        
        print(f"\n📄 Contract verwendet Solidity Version: ", end="")
        if 'pragma solidity' in contract_code:
            pragma_line = [line for line in contract_code.split('\n') if 'pragma solidity' in line][0]
            print(pragma_line.strip())
        else:
            print("Unbekannt")
            
    except FileNotFoundError:
        print("✗ wCAS.sol nicht gefunden")
    except Exception as e:
        print(f"✗ Fehler beim Analysieren: {e}")
    
    print("\n" + "=" * 60)
    print("NÄCHSTE SCHRITTE:")
    print("1. Führe das Debug-Script aus: python simple_mint_debug.py")
    print("2. Stelle sicher, dass du die korrekten Daten verwendest")
    print("3. Kontaktiere den Contract-Owner falls nötig")
    print("=" * 60)

if __name__ == "__main__":
    analyze_contract_issues() 