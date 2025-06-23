#!/usr/bin/env python3
"""
Fix für PolygonService - Behebt Meta-Transaction Probleme
Erstellt eine korrigierte Version der mint_wcas Funktion
"""

def show_polygon_service_fix():
    print("=" * 60)
    print("POLYGON SERVICE FIX")
    print("Lösung für Meta-Transaction Probleme")
    print("=" * 60)
    
    print("\n🔧 PROBLEM:")
    print("Ihr wCAS Contract verwendet _msgSender() (Meta-Transactions)")
    print("Aber Ihre App sendet normale Transaktionen")
    print("→ Contract erkennt Sie nicht als berechtigt")
    
    print("\n💡 LÖSUNG:")
    print("Verwenden Sie diese korrigierte mint_wcas Funktion:")
    print()
    
    fix_code = '''
def mint_wcas(self, recipient_address: str, amount_cas: float) -> Optional[str]:
    """
    KORRIGIERTE Version - kompatibel mit Meta-Transaction Contracts
    """
    try:
        amount_wei = int(amount_cas * (10**self.wcas_decimals))
        logger.info(f"=== STARTING wCAS MINT PROCESS (META-TX COMPATIBLE) ===")
        logger.info(f"Recipient: {recipient_address}")
        logger.info(f"Amount: {amount_cas} CAS = {amount_wei} wei")
        logger.info(f"Minter address: {self.minter_address}")
        
        # Wichtige Checks
        if not self.web3.is_connected():
            logger.error("Web3 nicht verbunden")
            return None
            
        # Adresse validieren und checksummen
        try:
            checksum_to_address = Web3.to_checksum_address(recipient_address)
        except Exception as e:
            logger.error(f"Ungültige Empfänger-Adresse: {e}")
            return None
            
        if amount_wei <= 0:
            logger.error("Betrag muss größer als 0 sein")
            return None
        
        # Nonce und Gas Parameter
        nonce = self.web3.eth.get_transaction_count(self.minter_address)
        
        # WICHTIG: Höheres Gas Limit für Meta-Transaction Contracts
        gas_limit = 200000  # Erhöht von Standard
        
        # Transaction Parameter (OHNE Meta-Transaction Headers)
        tx_params = {
            'from': self.minter_address,
            'nonce': nonce,
            'gas': gas_limit,  # Höheres Limit
        }
        
        # Gas Price Setup
        try:
            if self.chain_id in [137, 80001]:  # Polygon/Mumbai
                # EIP-1559 Fees
                last_block = self.web3.eth.get_block('latest')
                base_fee = last_block['baseFeePerGas']
                
                priority_fee = self.web3.to_wei(30, 'gwei')  # Standard priority
                max_fee = int(base_fee * 2) + priority_fee   # 2x buffer
                
                tx_params.update({
                    'maxPriorityFeePerGas': priority_fee,
                    'maxFeePerGas': max_fee,
                    'type': '0x2'
                })
            else:
                tx_params['gasPrice'] = self.web3.eth.gas_price
        except Exception as e:
            logger.warning(f"EIP-1559 Setup fehlgeschlagen: {e}")
            tx_params['gasPrice'] = self.web3.eth.gas_price
        
        logger.debug(f"Transaction params: {tx_params}")
        
        # Transaction erstellen
        try:
            transaction = self.wcas_contract.functions.mint(
                checksum_to_address, 
                amount_wei
            ).build_transaction(tx_params)
        except Exception as e:
            logger.error(f"Transaction Build Fehler: {e}")
            if "not minter" in str(e).lower():
                logger.error("MINTER PERMISSION ERROR - prüfen Sie Contract Setup!")
            return None
        
        # Transaction signieren
        signed_tx = self.minter_account.sign_transaction(transaction)
        
        # Transaction senden
        try:
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            if hasattr(tx_hash, 'hex'):
                final_tx_hash = tx_hash.hex()
            else:
                final_tx_hash = str(tx_hash)
                
            logger.info(f"Transaction gesendet: {final_tx_hash}")
            
            # Warten auf Receipt
            try:
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt.status == 1:
                    logger.info("✅ MINT ERFOLGREICH!")
                    logger.info(f"Block: {receipt.blockNumber}")
                    logger.info(f"Gas verbraucht: {receipt.gasUsed}")
                    return final_tx_hash
                else:
                    logger.error("❌ TRANSACTION FEHLGESCHLAGEN!")
                    logger.error(f"Receipt Status: {receipt.status}")
                    logger.error("Mögliche Ursachen:")
                    logger.error("- Meta-Transaction Setup Problem")
                    logger.error("- Ungültige Parameter")
                    logger.error("- Gas zu niedrig")
                    return None
                    
            except Exception as wait_error:
                logger.error(f"Timeout beim Warten auf Receipt: {wait_error}")
                return final_tx_hash  # Hash zurückgeben für manuelle Prüfung
                
        except Exception as send_error:
            logger.error(f"Fehler beim Senden: {send_error}")
            return None
            
    except Exception as e:
        logger.error(f"Allgemeiner Mint Fehler: {e}", exc_info=True)
        return None
'''
    
    print(fix_code)
    
    print("\n🎯 WICHTIGE ÄNDERUNGEN:")
    print("1. ✅ Höheres Gas Limit (200,000)")
    print("2. ✅ Bessere Fehlerbehandlung")
    print("3. ✅ Keine Meta-Transaction Header") 
    print("4. ✅ Detailliertes Logging")
    print("5. ✅ Validierung von Parametern")
    
    print("\n📝 ZUSÄTZLICHE CHECKS:")
    print("- Empfänger-Adresse Validierung")
    print("- Betrag > 0 Validierung")
    print("- Connection Status Check")
    print("- Receipt Status Analyse")
    
    print("\n⚠️ WENN DAS NICHT HILFT:")
    print("1. Führen Sie debug_meta_transaction_issue.py aus")
    print("2. Prüfen Sie den Trusted Forwarder im Contract")
    print("3. Eventuell Contract ohne Meta-TX neu deployen")
    
    print("\n" + "=" * 60)
    print("ANWENDUNG:")
    print("Ersetzen Sie Ihre mint_wcas Funktion in polygon_service.py")
    print("mit dem obigen Code")
    print("=" * 60)

if __name__ == "__main__":
    show_polygon_service_fix() 