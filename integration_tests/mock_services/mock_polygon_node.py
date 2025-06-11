from flask import Flask, jsonify, request
from decimal import Decimal
import time

app = Flask(__name__)

# Simulate wCAS balances on Polygon
WCAS_BALANCES = {}
MINT_LOG = []
BURN_LOG = []
TOTAL_SUPPLY = Decimal('0')

# Define the bridge's Polygon address for receiving wCAS deposits
BRIDGE_POLYGON_ADDRESS = "0xBridgePolygonAddress"

# Downtime simulation flag
SIMULATE_DOWNTIME = False
DOWNTIME_MESSAGE = "Mock Polygon Node: Service Unavailable (Simulated Downtime)"
DOWNTIME_STATUS_CODE = 503

# --- Watcher-related endpoints (wCAS -> Cas) ---
# The primary way a Polygon watcher detects deposits to the bridge is by monitoring
# Transfer events to BRIDGE_POLYGON_ADDRESS or by checking its balance.
# We don't need a specific "get_new_deposits" endpoint if the watcher scans blocks/events.
# The `/wcas/transfer_to_bridge` endpoint simulates the event occurring on-chain.
# If a watcher directly queries contract state or events, those queries would fail during downtime.
# For example, if it uses eth_getLogs or similar:
@app.route('/eth/getLogs', methods=['POST']) # Example of a common RPC call a watcher might use
def get_logs():
    if SIMULATE_DOWNTIME:
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE
    # Simulate a successful response (e.g., empty if no new events, or with mock events)
    print("Mock Polygon: Called /eth/getLogs (or similar event query endpoint)")
    # In a real mock, you might return events based on what `/wcas/transfer_to_bridge` logged.
    return jsonify([]), 200

# --- Bridge Backend related endpoints (Cas -> wCAS) ---
@app.route('/wcas/mint', methods=['POST'])
def mint_wcas():
    global TOTAL_SUPPLY
    if SIMULATE_DOWNTIME: # Also make backend-facing endpoints fail
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE

    data = request.json
    address, amount_str = data.get('address'), data.get('amount')
    if not address or amount_str is None: return jsonify({'error': 'Missing address or amount'}), 400
    try:
        amount = Decimal(str(amount_str))
        if amount <= 0: return jsonify({'error': 'Amount must be positive'}), 400
    except Exception:
        return jsonify({'error': 'Invalid amount format'}), 400

    WCAS_BALANCES[address] = WCAS_BALANCES.get(address, Decimal('0')) + amount
    TOTAL_SUPPLY += amount
    MINT_LOG.append({'to': address, 'amount': str(amount)}) # Store as string
    print(f"Mock Polygon: Minted {amount_str} wCAS for {address}. New bal: {WCAS_BALANCES[address]}. TotalSupply: {TOTAL_SUPPLY}")
    return jsonify({'tx_hash': f'mock_poly_mint_tx_{len(MINT_LOG)}', 'status': 'success'}), 200

@app.route('/wcas/burn', methods=['POST'])
def burn_wcas():
    global TOTAL_SUPPLY
    if SIMULATE_DOWNTIME:
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE

    data = request.json
    address_to_burn_from, amount_str = data.get('address', BRIDGE_POLYGON_ADDRESS), data.get('amount')
    if not address_to_burn_from or amount_str is None: return jsonify({'error': 'Missing address or amount for burn'}), 400
    try:
        amount = Decimal(str(amount_str))
        if amount <= 0: return jsonify({'error': 'Burn amount must be positive'}), 400
    except Exception:
        return jsonify({'error': 'Invalid burn amount format'}), 400

    if WCAS_BALANCES.get(address_to_burn_from, Decimal('0')) < amount:
        return jsonify({'error': 'Insufficient balance to burn', 'address': address_to_burn_from}), 400

    WCAS_BALANCES[address_to_burn_from] -= amount
    TOTAL_SUPPLY -= amount
    BURN_LOG.append({'from': address_to_burn_from, 'amount': str(amount)}) # Store as string
    print(f"Mock Polygon: Burned {amount_str} wCAS from {address_to_burn_from}. New bal: {WCAS_BALANCES[address_to_burn_from]}. TS: {TOTAL_SUPPLY}")
    return jsonify({'tx_hash': f'mock_poly_burn_tx_{len(BURN_LOG)}', 'status': 'success'}), 200

# --- Generic/Query Endpoints ---
@app.route('/wcas/balanceOf/<address>', methods=['GET'])
def get_wcas_balance(address):
    if SIMULATE_DOWNTIME:
        # Allow balance checks for verification during downtime tests, but could also fail them.
        # For watcher resilience, the critical part is that event fetching or state-changing calls fail.
        # Let's assume balanceOf might be used by watcher to confirm state post-event.
        print(DOWNTIME_MESSAGE + " (balanceOf might still work or fail depending on watcher needs)")
        # return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE
    balance = WCAS_BALANCES.get(address, Decimal('0'))
    print(f"Mock Polygon: Called balanceOf for {address}. Balance: {balance}")
    return jsonify({'address': address, 'balance': str(balance)})

@app.route('/wcas/totalSupply', methods=['GET'])
def get_wcas_total_supply():
    if SIMULATE_DOWNTIME:
        print(DOWNTIME_MESSAGE)
        return jsonify({'error': DOWNTIME_MESSAGE}), DOWNTIME_STATUS_CODE
    return jsonify({'totalSupply': str(TOTAL_SUPPLY)})

# --- Test Helper Endpoints ---
# This simulates a user's wallet transferring wCAS to the bridge's address.
# This endpoint itself should work during downtime simulation as it's a test setup method.
@app.route('/wcas/transfer_to_bridge', methods=['POST'])
def transfer_to_bridge():
    data = request.json
    from_address, amount_str = data.get('from_address'), data.get('amount')
    if not from_address or amount_str is None: return jsonify({'error': 'Missing from_address or amount'}), 400
    try:
        amount = Decimal(str(amount_str))
        if amount < 0: return jsonify({'error': 'Transfer amount cannot be negative'}), 400
    except Exception:
        return jsonify({'error': 'Invalid amount format'}), 400

    if WCAS_BALANCES.get(from_address, Decimal('0')) < amount:
        return jsonify({'error': 'Insufficient balance for transfer'}), 400

    tx_hash_sim = f'mock_poly_transfer_tx_{from_address}_{amount_str}_{time.time_ns()}'
    if amount == 0:
        print(f"Mock Polygon: Received transfer of 0 wCAS from {from_address} to {BRIDGE_POLYGON_ADDRESS} (tx: {tx_hash_sim}).")
        # The watcher would see this transaction to the bridge address with value 0
        # We can log this as a "detected" event for the watcher to pick up if it queries an event log.
        # For simplicity, the test will focus on the watcher being able to query *something* like getLogs.
        return jsonify({'tx_hash': tx_hash_sim, 'status': 'success_zero_amount'}), 200

    WCAS_BALANCES[from_address] -= amount
    WCAS_BALANCES[BRIDGE_POLYGON_ADDRESS] = WCAS_BALANCES.get(BRIDGE_POLYGON_ADDRESS, Decimal('0')) + amount
    print(f"Mock Polygon: Transferred {amount_str} wCAS from {from_address} to {BRIDGE_POLYGON_ADDRESS} (tx: {tx_hash_sim}).")
    print(f"Mock Polygon: Bal {from_address}: {WCAS_BALANCES[from_address]}, Bal {BRIDGE_POLYGON_ADDRESS}: {WCAS_BALANCES[BRIDGE_POLYGON_ADDRESS]}")
    return jsonify({'tx_hash': tx_hash_sim, 'status': 'success'}), 200

@app.route('/test/get_mint_log', methods=['GET'])
def get_mint_log(): return jsonify(MINT_LOG)

@app.route('/test/get_burn_log', methods=['GET'])
def get_burn_log(): return jsonify(BURN_LOG)

@app.route('/test/reset', methods=['POST'])
def reset_state():
    global WCAS_BALANCES, MINT_LOG, BURN_LOG, TOTAL_SUPPLY, SIMULATE_DOWNTIME
    WCAS_BALANCES, MINT_LOG, BURN_LOG = {}, [], []
    TOTAL_SUPPLY = Decimal('0')
    SIMULATE_DOWNTIME = False # Ensure downtime is off on reset
    print(f"Mock Polygon: ALL STATE RESET. Downtime: {SIMULATE_DOWNTIME}")
    return jsonify({'message': 'Mock Polygon state reset successfully'}), 200

@app.route('/test/simulate_downtime', methods=['POST'])
def set_downtime():
    global SIMULATE_DOWNTIME
    data = request.json
    action = data.get('action', 'start') # 'start' or 'end'
    if action == 'start':
        SIMULATE_DOWNTIME = True
        print("Mock Polygon: SIMULATING DOWNTIME START")
        return jsonify({'message': 'Downtime started'}), 200
    elif action == 'end':
        SIMULATE_DOWNTIME = False
        print("Mock Polygon: SIMULATING DOWNTIME END")
        return jsonify({'message': 'Downtime ended'}), 200
    return jsonify({'error': 'Invalid action for downtime simulation'}), 400

if __name__ == '__main__':
    app.run(port=5002, debug=True)
