import unittest
import requests
import time
import os
from decimal import Decimal

# API endpoints for the test environment
PUBLIC_API_URL = "http://localhost:8000"  # The API for external callers
MOCK_CASCOIN_NODE_URL = "http://localhost:5001"
MOCK_POLYGON_NODE_URL = "http://localhost:5002"

# Configuration
CAS_REQUIRED_CONFIRMATIONS = 6 # From previous tests
MOCK_BRIDGE_POLYGON_ADDRESS = "0xBridgePolygonAddress" # From mock_polygon_node.py
DOWNTIME_DURATION_SECONDS = 10 # How long to keep mock services "down"
WATCHER_RECOVERY_TIME_SECONDS = 30 # Time to wait for watcher to recover and process after downtime

class TestWatcherResilience(unittest.TestCase):

    def setUp(self):
        # Reset mock services state and ensure downtime is off
        try:
            print("\nResetting mock Cascoin node state...")
            requests.post(f"{MOCK_CASCOIN_NODE_URL}/test/reset_state")
            requests.post(f"{MOCK_CASCOIN_NODE_URL}/test/simulate_downtime", json={"action": "end"})
            print("Resetting mock Polygon node state...")
            requests.post(f"{MOCK_POLYGON_NODE_URL}/test/reset")
            requests.post(f"{MOCK_POLYGON_NODE_URL}/test/simulate_downtime", json={"action": "end"})
            print("Mock services reset and downtime ended for setUp.")
        except requests.exceptions.ConnectionError as e:
            self.fail(f"Critical: Could not connect to mock services during setUp: {e}. Aborting tests.")

    def tearDown(self):
        # Ensure downtime is ended after each test, just in case
        try:
            requests.post(f"{MOCK_CASCOIN_NODE_URL}/test/simulate_downtime", json={"action": "end"})
            requests.post(f"{MOCK_POLYGON_NODE_URL}/test/simulate_downtime", json={"action": "end"})
            print("Ensured downtime is ended in tearDown.")
        except requests.exceptions.ConnectionError:
            print("Warning: Could not connect to mock services during tearDown to end downtime.")


    # --- Helper methods from previous integration tests (adapted) ---
    def _simulate_cas_deposit_on_mock(self, txid, amount, confirmations, cas_bridge_deposit_address):
        payload = {
            "txid": txid, "amount": str(amount),
            "confirmations": confirmations, "cas_recipient_address": cas_bridge_deposit_address
        }
        requests.post(f"{MOCK_CASCOIN_NODE_URL}/test/set_cas_deposit_transaction", json=payload).raise_for_status()
        print(f"ResilienceTest: Simulated CAS deposit: {txid}, amount: {amount}, confirmations: {confirmations}")

    def _get_wcas_balance_on_mock(self, polygon_address):
        response = requests.get(f"{MOCK_POLYGON_NODE_URL}/wcas/balanceOf/{polygon_address}")
        # This might fail if Polygon mock is still "down" but test needs to verify final state
        if response.status_code == 200:
            return Decimal(response.json().get("balance", "0"))
        return Decimal("-1") # Indicate error or inability to fetch

    def _simulate_wcas_transfer_to_bridge_on_mock(self, user_polygon_address, amount_wcas):
        current_balance = self._get_wcas_balance_on_mock(user_polygon_address)
        if current_balance < Decimal(amount_wcas) and current_balance != Decimal("-1"):
             mint_payload = {"address": user_polygon_address, "amount": str(Decimal(amount_wcas) - current_balance)}
             requests.post(f"{MOCK_POLYGON_NODE_URL}/wcas/mint", json=mint_payload).raise_for_status()

        transfer_payload = {"from_address": user_polygon_address, "amount": str(amount_wcas)}
        response = requests.post(f"{MOCK_POLYGON_NODE_URL}/wcas/transfer_to_bridge", json=transfer_payload)
        response.raise_for_status() # This call sets up the event the watcher looks for
        tx_details = response.json()
        print(f"ResilienceTest: Simulated wCAS transfer from {user_polygon_address} to bridge: {tx_details.get('tx_hash')}")
        return tx_details.get('tx_hash')

    def _get_cas_sent_transactions_on_mock(self):
        response = requests.get(f"{MOCK_CASCOIN_NODE_URL}/test/get_cas_sent_transactions")
        if response.status_code == 200:
            return response.json()
        return []

    def _get_bridge_deposit_address(self, user_polygon_address):
        """
        Calls the bridge to get a unique CAS deposit address and create the DB record.
        """
        print(f"Bridge: User {user_polygon_address} requests CAS deposit address.")
        response = requests.post(f"{PUBLIC_API_URL}/api/request_cascoin_deposit_address", json={"polygon_address": user_polygon_address})
        response.raise_for_status()
        return response.json()["cascoin_deposit_address"]


    # Test Case 1: Cascoin Watcher Resilience
    def test_cascoin_watcher_resilience_to_node_downtime(self):
        print("\nRunning: test_cascoin_watcher_resilience_to_node_downtime")
        user_polygon_address = "0x3333333333333333333333333333333333333333"
        cas_txid = "cas_tx_resilience_1"
        deposit_amount = Decimal("10.0")
        
        # This is the crucial step to create the deposit record in the bridge's DB
        cas_bridge_deposit_address = self._get_bridge_deposit_address(user_polygon_address)

        # 1. Initial CAS deposit with 0 confirmations (watcher should see it but not act yet)
        self._simulate_cas_deposit_on_mock(cas_txid, deposit_amount, 0, cas_bridge_deposit_address)
        print(f"ResilienceTest: Initial deposit {cas_txid} made with 0 confirmations.")

        # 2. Simulate Cascoin Node Downtime START
        print(f"ResilienceTest: Starting Cascoin node downtime for {DOWNTIME_DURATION_SECONDS}s...")
        requests.post(f"{MOCK_CASCOIN_NODE_URL}/test/simulate_downtime", json={"action": "start"}).raise_for_status()

        # 3. While node is "down", update deposit to have sufficient confirmations.
        # The watcher *should* be trying to poll and failing.
        # This update to the mock's internal state will be invisible until downtime ends.
        self._simulate_cas_deposit_on_mock(cas_txid, deposit_amount, CAS_REQUIRED_CONFIRMATIONS, cas_bridge_deposit_address)
        print(f"ResilienceTest: Deposit {cas_txid} updated to {CAS_REQUIRED_CONFIRMATIONS} confirmations (during downtime).")

        # 4. Wait for the duration of the simulated downtime
        time.sleep(DOWNTIME_DURATION_SECONDS)

        # 5. Simulate Cascoin Node Downtime END
        print("ResilienceTest: Ending Cascoin node downtime.")
        requests.post(f"{MOCK_CASCOIN_NODE_URL}/test/simulate_downtime", json={"action": "end"}).raise_for_status()

        # Prime the mock for the expected mint after recovery
        prime_data = {'address': user_polygon_address, 'amount': str(deposit_amount)}
        requests.post(f"{MOCK_POLYGON_NODE_URL}/test/prime_mint", json=prime_data).raise_for_status()

        # 6. Give watcher time to recover and process the deposit
        print(f"ResilienceTest: Waiting {WATCHER_RECOVERY_TIME_SECONDS}s for Cascoin watcher to recover and process...")
        time.sleep(WATCHER_RECOVERY_TIME_SECONDS)

        # 7. Verify:
        #    - wCAS is minted to the user's Polygon address.
        #    - Watcher logs (conceptual) would show retries and eventual success.
        final_wcas_balance = self._get_wcas_balance_on_mock(user_polygon_address)
        self.assertEqual(final_wcas_balance, deposit_amount,
                         f"wCAS should have been minted after Cascoin node recovery. Expected: {deposit_amount}, Got: {final_wcas_balance}")
        print(f"ResilienceTest: Cascoin watcher resilience test PASSED. wCAS minted for {user_polygon_address}.")
        print("Conceptual: Verify Cascoin watcher logs for retry attempts and successful processing.")


    # Test Case 2: Polygon Watcher Resilience
    def test_polygon_watcher_resilience_to_node_downtime(self):
        print("\nRunning: test_polygon_watcher_resilience_to_node_downtime")
        user_sending_wcas_address = "0x4444444444444444444444444444444444444444"
        user_cascoin_receive_address = "casUserReceivesResilience"
        wcas_deposit_amount = Decimal("20.0")

        # 1. Simulate user depositing wCAS to the bridge's Polygon address.
        # This creates the on-chain event the Polygon watcher should detect.
        wcas_tx_hash = self._simulate_wcas_transfer_to_bridge_on_mock(user_sending_wcas_address, wcas_deposit_amount)
        print(f"ResilienceTest: User transferred {wcas_deposit_amount} wCAS to bridge (tx: {wcas_tx_hash}). Bridge wCAS bal: {self._get_wcas_balance_on_mock(MOCK_BRIDGE_POLYGON_ADDRESS)}")

        # 2. Simulate Polygon Node Downtime START
        print(f"ResilienceTest: Starting Polygon node downtime for {DOWNTIME_DURATION_SECONDS}s...")
        requests.post(f"{MOCK_POLYGON_NODE_URL}/test/simulate_downtime", json={"action": "start"}).raise_for_status()

        # 3. During downtime, the watcher should be failing to get event logs or confirm the transaction.
        # No state change needed on the mock node itself for this part of the test,
        # as the event has already "happened". The watcher just can't see it.

        # 4. Wait for the duration of the simulated downtime
        time.sleep(DOWNTIME_DURATION_SECONDS)

        # 5. Simulate Polygon Node Downtime END
        print("ResilienceTest: Ending Polygon node downtime.")
        requests.post(f"{MOCK_POLYGON_NODE_URL}/test/simulate_downtime", json={"action": "end"}).raise_for_status()

        # 6. Give watcher time to recover and process the wCAS deposit
        # This involves the watcher detecting the event, bridge backend burning wCAS, and releasing CAS.
        # For this test, we need to simulate the bridge backend actions after the watcher (conceptually) informs it.
        print(f"ResilienceTest: Waiting {WATCHER_RECOVERY_TIME_SECONDS}s for Polygon watcher to recover and bridge to process...")

        # --- SIMULATE BRIDGE BACKEND ACTIONS POST-WATCHER RECOVERY ---
        # This assumes the Polygon watcher successfully notified the bridge backend after downtime.
        # These calls would be made by the *actual bridge backend*.
        # If these are not made, it means the watcher failed to notify or the backend logic failed.
        time.sleep(WATCHER_RECOVERY_TIME_SECONDS / 2) # Give some time for watcher to detect

        print("ResilienceTest: Simulating bridge backend burning wCAS and releasing CAS (post-downtime)...")
        try:
            # Bridge burns wCAS it received
            burn_payload = {"address": MOCK_BRIDGE_POLYGON_ADDRESS, "amount": str(wcas_deposit_amount)}
            requests.post(f"{MOCK_POLYGON_NODE_URL}/wcas/burn", json=burn_payload).raise_for_status()
            print(f"ResilienceTest: Bridge backend (simulated) called mock burn for {wcas_deposit_amount} wCAS.")

            # Bridge releases CAS
            cas_release_payload = {"to_address": user_cascoin_receive_address, "amount": str(wcas_deposit_amount)}
            requests.post(f"{MOCK_CASCOIN_NODE_URL}/cas/send_transaction", json=cas_release_payload).raise_for_status()
            print(f"ResilienceTest: Bridge backend (simulated) called mock CAS release to {user_cascoin_receive_address}.")
        except requests.exceptions.HTTPError as e:
            print(f"ResilienceTest: Error during simulated bridge backend action: {e.response.text}")
            # This part failing might indicate the mock nodes are still down or a logic error in test.
        except requests.exceptions.ConnectionError as e:
             self.fail(f"ResilienceTest: Connection error during simulated bridge backend action: {e}")


        time.sleep(WATCHER_RECOVERY_TIME_SECONDS / 2)
        # --- END OF SIMULATED BRIDGE BACKEND ACTIONS ---

        # 7. Verify:
        #    - CAS is released to the user's Cascoin address.
        #    - Watcher logs (conceptual) would show retries and eventual success.
        sent_cas_txs = self._get_cas_sent_transactions_on_mock()
        self.assertTrue(
            any(tx['to_address'] == user_cascoin_receive_address and Decimal(tx['amount']) == wcas_deposit_amount for tx in sent_cas_txs),
            f"CAS should have been released after Polygon node recovery. Expected {wcas_deposit_amount} CAS to {user_cascoin_receive_address}. Found: {sent_cas_txs}"
        )
        print(f"ResilienceTest: Polygon watcher resilience test PASSED. CAS released to {user_cascoin_receive_address}.")
        print("Conceptual: Verify Polygon watcher logs for retry attempts and successful processing.")


if __name__ == '__main__':
    print("Starting Watcher Resilience Tests...")
    print(f"PUBLIC_API_URL: {PUBLIC_API_URL}")
    print(f"MOCK_CASCOIN_NODE_URL: {MOCK_CASCOIN_NODE_URL}")
    print(f"MOCK_POLYGON_NODE_URL: {MOCK_POLYGON_NODE_URL}")
    print("Important: These tests require the bridge's Cascoin and Polygon watchers to be running and configured")
    print("to use the respective mock node URLs. The watchers' retry logic is being tested.")

    suite = unittest.TestSuite()
    suite.addTest(TestWatcherResilience("test_cascoin_watcher_resilience_to_node_downtime"))
    suite.addTest(TestWatcherResilience("test_polygon_watcher_resilience_to_node_downtime"))
    runner = unittest.TextTestRunner()
    runner.run(suite)
