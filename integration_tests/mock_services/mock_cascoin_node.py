from flask import Flask, jsonify, request
from decimal import Decimal
import time

app = Flask(__name__)

# Simulate a database of transactions and their confirmations for Cas->wCAS flow
MOCK_CASCOIN_DEPOSIT_TRANSACTIONS = {}
MOCK_DEPOSITS_INFO = {} # Stores amount, recipient for deposits to bridge

# Simulate bridge's hot wallet and outgoing CAS transactions for wCAS->Cas flow
CAS_HOT_WALLET_BALANCE = Decimal('10000.0') # Initial balance for testing
CAS_SENT_TRANSACTIONS = []

# Downtime simulation flag
SIMULATE_DOWNTIME = False
DOWNTIME_MESSAGE = "Mock Cascoin Node: Service Unavailable (Simulated Downtime)"
DOWNTIME_STATUS_CODE = 503

# --- Watcher-related endpoints (Cas -> wCAS) ---
@app.route('/get_transaction_confirmations/<txid>', methods=['GET'])
def get_transaction_confirmations(txid):
    if SIMULATE_DOWNTIME:
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE

    confirmations = MOCK_CASCOIN_DEPOSIT_TRANSACTIONS.get(txid, {}).get('confirmations', 0)
    print(f"Mock Cascoin: Called get_transaction_confirmations for {txid}. Confirmations: {confirmations}")
    return jsonify({'txid': txid, 'confirmations': confirmations})

@app.route('/get_deposit_info/<txid>', methods=['GET'])
def get_deposit_info(txid):
    if SIMULATE_DOWNTIME:
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE

    deposit = MOCK_DEPOSITS_INFO.get(txid)
    if deposit:
        print(f"Mock Cascoin: Called get_deposit_info for {txid}. Info: {deposit}")
        return jsonify(deposit)
    print(f"Mock Cascoin: Called get_deposit_info for {txid}. Deposit not found.")
    return jsonify({'error': 'Deposit not found'}), 404

# --- Bridge Backend related endpoints (wCAS -> Cas, Hot Wallet) ---
@app.route('/cas/send_transaction', methods=['POST'])
def send_cas_transaction():
    global CAS_HOT_WALLET_BALANCE
    if SIMULATE_DOWNTIME: # Also make backend-facing endpoints fail during general downtime
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE

    data = request.json
    to_address = data.get('to_address')
    amount_str = data.get('amount')

    if not to_address or amount_str is None:
        return jsonify({'error': 'Missing to_address or amount for sending CAS'}), 400
    try:
        amount = Decimal(str(amount_str))
        if amount <= 0: return jsonify({'error': 'CAS send amount must be positive'}), 400
    except Exception:
        return jsonify({'error': 'Invalid CAS send amount format'}), 400

    if CAS_HOT_WALLET_BALANCE < amount:
        print(f"Mock Cascoin (Hot Wallet): Insufficient funds to send {amount_str} CAS to {to_address}. Balance: {CAS_HOT_WALLET_BALANCE}")
        return jsonify({'error': 'Insufficient hot wallet balance'}), 500

    CAS_HOT_WALLET_BALANCE -= amount
    tx_receipt = {
        'txid': f'mock_cas_sent_tx_{len(CAS_SENT_TRANSACTIONS) + 1}',
        'to_address': to_address, 'amount': str(amount), 'status': 'SUCCESS'
    }
    CAS_SENT_TRANSACTIONS.append(tx_receipt)
    print(f"Mock Cascoin (Hot Wallet): Sent {amount_str} CAS to {to_address}. Hot Wallet Balance: {CAS_HOT_WALLET_BALANCE}")
    return jsonify(tx_receipt), 200

@app.route('/cas/get_hot_wallet_balance', methods=['GET'])
def get_hot_wallet_balance():
    if SIMULATE_DOWNTIME:
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE
    return jsonify({'balance': str(CAS_HOT_WALLET_BALANCE)})

# --- Test Helper Endpoints ---
@app.route('/test/set_cas_deposit_transaction', methods=['POST'])
def set_cas_deposit_transaction():
    # This endpoint is for test setup, should ideally work even during "downtime"
    # or tests should ensure downtime ends before trying to set up next test.
    data = request.json
    txid = data.get('txid')
    confirmations = data.get('confirmations')
    amount_str = data.get('amount')
    cas_recipient_address = data.get('cas_recipient_address')

    if not txid or confirmations is None or amount_str is None or cas_recipient_address is None:
        return jsonify({'error': 'Missing data for setting CAS deposit tx'}), 400
    try:
        amount = Decimal(str(amount_str))
    except Exception:
        return jsonify({'error': 'Invalid amount format for CAS deposit tx'}), 400

    MOCK_CASCOIN_DEPOSIT_TRANSACTIONS[txid] = {'confirmations': confirmations}
    MOCK_DEPOSITS_INFO[txid] = {
        'txid': txid, 'amount': str(amount), 'cas_recipient_address': cas_recipient_address,
    }
    print(f"Mock Cascoin (Deposit Sim): Set TX {txid} to bridge addr {cas_recipient_address} with {confirmations} conf, amount {amount_str}")
    return jsonify({'message': f'CAS Deposit Transaction {txid} set'}), 200

@app.route('/test/get_cas_sent_transactions', methods=['GET'])
def get_cas_sent_transactions():
    # Test helper, should work during downtime for verification purposes.
    return jsonify(CAS_SENT_TRANSACTIONS)

@app.route('/test/reset_state', methods=['POST']) # Renamed for clarity
def reset_state():
    global CAS_HOT_WALLET_BALANCE, CAS_SENT_TRANSACTIONS, MOCK_CASCOIN_DEPOSIT_TRANSACTIONS, MOCK_DEPOSITS_INFO, SIMULATE_DOWNTIME
    data = request.json if request.data else {}
    initial_balance = data.get('initial_balance', '10000.0')

    CAS_HOT_WALLET_BALANCE = Decimal(initial_balance)
    CAS_SENT_TRANSACTIONS = []
    MOCK_CASCOIN_DEPOSIT_TRANSACTIONS = {}
    MOCK_DEPOSITS_INFO = {}
    SIMULATE_DOWNTIME = False # Ensure downtime is off on reset
    print(f"Mock Cascoin: ALL STATE RESET. Hot Wallet Balance: {CAS_HOT_WALLET_BALANCE}. Downtime: {SIMULATE_DOWNTIME}")
    return jsonify({'message': 'Mock Cascoin state reset successfully'}), 200

@app.route('/test/simulate_downtime', methods=['POST'])
def set_downtime():
    global SIMULATE_DOWNTIME
    data = request.json
    action = data.get('action', 'start') # 'start' or 'end'
    if action == 'start':
        SIMULATE_DOWNTIME = True
        print("Mock Cascoin: SIMULATING DOWNTIME START")
        return jsonify({'message': 'Downtime started'}), 200
    elif action == 'end':
        SIMULATE_DOWNTIME = False
        print("Mock Cascoin: SIMULATING DOWNTIME END")
        return jsonify({'message': 'Downtime ended'}), 200
    return jsonify({'error': 'Invalid action for downtime simulation'}), 400

if __name__ == '__main__':
    app.run(port=5001, debug=True)
