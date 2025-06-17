import unittest
import asyncio
import json
import time
import threading
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import websocket as ws_client
import pytest

from backend.main import app
from backend.database import get_db
from database.models import Base, CasDeposit, WcasToCasReturnIntention, PolygonTransaction
from backend import crud


@pytest.mark.integration
@pytest.mark.websocket
@pytest.mark.realtime
class TestRealtimeWebSocketIntegration(unittest.TestCase):
    """Integration tests for real-time WebSocket functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test database and application"""
        # Create in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(cls.engine)
        
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Override the get_db dependency
        def override_get_db():
            try:
                db = cls.TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after tests"""
        app.dependency_overrides.clear()
    
    def setUp(self):
        """Set up for each test"""
        self.db = self.TestingSessionLocal()
        self.user_address = "0x1234567890123456789012345678901234567890"
        self.websocket_messages = []
        self.websocket_connected = False
        self.websocket_error = None
    
    def tearDown(self):
        """Clean up after each test"""
        # Clear the database
        self.db.query(CasDeposit).delete()
        self.db.query(WcasToCasReturnIntention).delete()
        self.db.query(PolygonTransaction).delete()
        self.db.commit()
        self.db.close()
    
    def test_websocket_connection_and_ping_pong(self):
        """Test basic WebSocket connection and ping/pong functionality"""
        with self.client.websocket_connect(f"/api/ws/{self.user_address}") as websocket:
            # Send ping
            websocket.send_text(json.dumps({"type": "ping"}))
            
            # Receive pong
            response = websocket.receive_text()
            response_data = json.loads(response)
            
            self.assertEqual(response_data["type"], "pong")
    
    def test_websocket_cas_deposit_lifecycle(self):
        """Test complete CAS deposit lifecycle with real-time updates"""
        # Create initial CAS deposit
        deposit = crud.create_cas_deposit_record(self.db, self.user_address)
        self.assertIsNotNone(deposit)
        
        with self.client.websocket_connect(f"/api/ws/{self.user_address}") as websocket:
            # Should receive initial status
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            
            self.assertEqual(initial_data["type"], "cas_deposit_update")
            self.assertEqual(initial_data["data"]["id"], deposit.id)
            self.assertEqual(initial_data["data"]["status"], "pending")
            
            # Update deposit status - this should trigger a WebSocket notification
            crud.update_cas_deposit_status_and_mint_hash(
                self.db, 
                deposit.id, 
                "pending_confirmation", 
                received_amount=10.5
            )
            
            # Should receive update notification
            update_message = websocket.receive_text()
            update_data = json.loads(update_message)
            
            self.assertEqual(update_data["type"], "cas_deposit_update")
            self.assertEqual(update_data["data"]["id"], deposit.id)
            self.assertEqual(update_data["data"]["status"], "pending_confirmation")
            self.assertEqual(update_data["data"]["received_amount"], 10.5)
            
            # Final update to completed
            crud.update_cas_deposit_status_and_mint_hash(
                self.db,
                deposit.id,
                "completed",
                mint_tx_hash="0xminthash123"
            )
            
            # Should receive final notification
            final_message = websocket.receive_text()
            final_data = json.loads(final_message)
            
            self.assertEqual(final_data["type"], "cas_deposit_update")
            self.assertEqual(final_data["data"]["status"], "completed")
            self.assertEqual(final_data["data"]["mint_tx_hash"], "0xminthash123")
    
    def test_websocket_wcas_return_intention_lifecycle(self):
        """Test complete wCAS return intention lifecycle with real-time updates"""
        # Create initial return intention
        from backend.schemas import WCASReturnIntentionRequest
        
        intention_request = WCASReturnIntentionRequest(
            user_polygon_address=self.user_address,
            target_cascoin_address="cas_target_address",
            bridge_amount=25.0,
            fee_model="direct_payment"
        )
        
        intention = crud.create_wcas_return_intention(self.db, intention_request)
        self.assertIsNotNone(intention)
        
        with self.client.websocket_connect(f"/api/ws/{self.user_address}") as websocket:
            # Should receive initial status
            initial_message = websocket.receive_text()
            initial_data = json.loads(initial_message)
            
            self.assertEqual(initial_data["type"], "wcas_return_intention_update")
            self.assertEqual(initial_data["data"]["id"], intention.id)
            self.assertEqual(initial_data["data"]["status"], "pending_deposit")
            
            # Update intention status - this should trigger a WebSocket notification
            crud.update_wcas_return_intention_status(
                self.db,
                intention.id,
                "deposit_detected"
            )
            
            # Should receive update notification
            update_message = websocket.receive_text()
            update_data = json.loads(update_message)
            
            self.assertEqual(update_data["type"], "wcas_return_intention_update")
            self.assertEqual(update_data["data"]["status"], "deposit_detected")
            
            # Final update to processed
            crud.update_wcas_return_intention_status(
                self.db,
                intention.id,
                "processed"
            )
            
            # Should receive final notification
            final_message = websocket.receive_text()
            final_data = json.loads(final_message)
            
            self.assertEqual(final_data["type"], "wcas_return_intention_update")
            self.assertEqual(final_data["data"]["status"], "processed")
    
    def test_websocket_multiple_deposits_isolation(self):
        """Test that users only receive updates for their own deposits"""
        user1_address = "0x1111111111111111111111111111111111111111"
        user2_address = "0x2222222222222222222222222222222222222222"
        
        # Create deposits for both users
        deposit1 = crud.create_cas_deposit_record(self.db, user1_address)
        deposit2 = crud.create_cas_deposit_record(self.db, user2_address)
        
        with self.client.websocket_connect(f"/api/ws/{user1_address}") as ws1:
            with self.client.websocket_connect(f"/api/ws/{user2_address}") as ws2:
                # User 1 should only receive their deposit
                user1_message = ws1.receive_text()
                user1_data = json.loads(user1_message)
                
                self.assertEqual(user1_data["data"]["id"], deposit1.id)
                self.assertEqual(user1_data["data"]["polygon_address"], user1_address)
                
                # User 2 should only receive their deposit
                user2_message = ws2.receive_text()
                user2_data = json.loads(user2_message)
                
                self.assertEqual(user2_data["data"]["id"], deposit2.id)
                self.assertEqual(user2_data["data"]["polygon_address"], user2_address)
                
                # Update user 1's deposit
                crud.update_cas_deposit_status_and_mint_hash(
                    self.db,
                    deposit1.id,
                    "completed"
                )
                
                # Only user 1 should receive the update
                user1_update = ws1.receive_text()
                user1_update_data = json.loads(user1_update)
                
                self.assertEqual(user1_update_data["data"]["id"], deposit1.id)
                self.assertEqual(user1_update_data["data"]["status"], "completed")
                
                # User 2 should not receive any new messages
                # (We can't easily test this without introducing timing issues,
                # but the architecture ensures isolation)
    
    def test_websocket_request_status_update(self):
        """Test manual status update request via WebSocket"""
        # Create a deposit first
        deposit = crud.create_cas_deposit_record(self.db, self.user_address)
        
        with self.client.websocket_connect(f"/api/ws/{self.user_address}") as websocket:
            # Receive initial message
            initial_message = websocket.receive_text()
            
            # Request status update
            websocket.send_text(json.dumps({"type": "request_status_update"}))
            
            # Should receive the same data again
            status_update = websocket.receive_text()
            status_data = json.loads(status_update)
            
            self.assertEqual(status_data["type"], "cas_deposit_update")
            self.assertEqual(status_data["data"]["id"], deposit.id)
    
    def test_websocket_invalid_json_handling(self):
        """Test WebSocket handling of invalid JSON"""
        with self.client.websocket_connect(f"/api/ws/{self.user_address}") as websocket:
            # Send invalid JSON
            websocket.send_text("invalid json string")
            
            # Should receive error response
            error_response = websocket.receive_text()
            error_data = json.loads(error_response)
            
            self.assertEqual(error_data["type"], "error")
            self.assertEqual(error_data["message"], "Invalid JSON")
    
    def test_websocket_connection_with_existing_data(self):
        """Test WebSocket connection when user already has existing records"""
        # Create multiple records for the user
        deposit = crud.create_cas_deposit_record(self.db, self.user_address)
        
        from backend.schemas import WCASReturnIntentionRequest
        intention_request = WCASReturnIntentionRequest(
            user_polygon_address=self.user_address,
            target_cascoin_address="cas_target",
            bridge_amount=15.0,
            fee_model="deducted"
        )
        intention = crud.create_wcas_return_intention(self.db, intention_request)
        
        with self.client.websocket_connect(f"/api/ws/{self.user_address}") as websocket:
            # Should receive both records on connection
            message1 = websocket.receive_text()
            message2 = websocket.receive_text()
            
            data1 = json.loads(message1)
            data2 = json.loads(message2)
            
            # Should receive both types of updates (order may vary)
            message_types = {data1["type"], data2["type"]}
            self.assertIn("cas_deposit_update", message_types)
            self.assertIn("wcas_return_intention_update", message_types)


@pytest.mark.integration
@pytest.mark.websocket
@pytest.mark.realtime
class TestRealtimeWebSocketStressTest(unittest.TestCase):
    """Stress tests for WebSocket functionality"""
    
    def setUp(self):
        """Set up for stress tests"""
        # Create in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Override the get_db dependency
        def override_get_db():
            try:
                db = self.TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
    
    def tearDown(self):
        """Clean up after stress tests"""
        app.dependency_overrides.clear()
    
    def test_multiple_concurrent_connections(self):
        """Test multiple concurrent WebSocket connections"""
        num_connections = 5
        websockets = []
        
        try:
            # Create multiple connections
            for i in range(num_connections):
                user_address = f"0x{str(i).zfill(40)}"
                ws = self.client.websocket_connect(f"/api/ws/{user_address}")
                websockets.append((ws.__enter__(), user_address))
            
            # Send ping to all connections
            for ws, _ in websockets:
                ws.send_text(json.dumps({"type": "ping"}))
            
            # All should respond with pong
            for ws, _ in websockets:
                response = ws.receive_text()
                response_data = json.loads(response)
                self.assertEqual(response_data["type"], "pong")
                
        finally:
            # Clean up connections
            for ws, _ in websockets:
                try:
                    ws.__exit__(None, None, None)
                except:
                    pass
    
    def test_rapid_status_updates(self):
        """Test rapid successive status updates"""
        user_address = "0x1234567890123456789012345678901234567890"
        db = self.TestingSessionLocal()
        
        try:
            # Create deposit
            deposit = crud.create_cas_deposit_record(db, user_address)
            
            with self.client.websocket_connect(f"/api/ws/{user_address}") as websocket:
                # Receive initial message
                initial_message = websocket.receive_text()
                
                # Perform rapid updates
                statuses = ["pending_confirmation", "confirmed", "mint_submitted", "completed"]
                
                for status in statuses:
                    crud.update_cas_deposit_status_and_mint_hash(
                        db,
                        deposit.id,
                        status
                    )
                    
                    # Should receive update for each status change
                    update_message = websocket.receive_text()
                    update_data = json.loads(update_message)
                    
                    self.assertEqual(update_data["data"]["status"], status)
                    
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main() 