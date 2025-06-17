import unittest
import json
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from sqlalchemy.orm import Session
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket, WebSocketDisconnect

# Modules and dependencies to test
from backend.api import websocket_api
from database.models import CasDeposit, WcasToCasReturnIntention, PolygonTransaction
from backend.database import get_db

# Test app setup
app = FastAPI()
app.include_router(websocket_api.router, prefix="/api")


@pytest.mark.unit
@pytest.mark.websocket
class TestConnectionManager(unittest.TestCase):
    """Test the WebSocket ConnectionManager class"""
    
    def setUp(self):
        self.manager = websocket_api.ConnectionManager()
        self.mock_websocket = MagicMock(spec=WebSocket)
        self.user_identifier = "0x1234567890123456789012345678901234567890"
    
    def test_connection_manager_init(self):
        """Test ConnectionManager initialization"""
        self.assertEqual(self.manager.active_connections, {})
    
    @patch.object(websocket_api.ConnectionManager, 'connect')
    async def test_connect_new_user(self, mock_connect):
        """Test connecting a new user"""
        await self.manager.connect(self.mock_websocket, self.user_identifier)
        
        self.assertIn(self.user_identifier, self.manager.active_connections)
        self.assertIn(self.mock_websocket, self.manager.active_connections[self.user_identifier])
        self.mock_websocket.accept.assert_called_once()
    
    def test_disconnect_existing_user(self):
        """Test disconnecting an existing user"""
        # Setup: add user to connections
        self.manager.active_connections[self.user_identifier] = [self.mock_websocket]
        
        # Test disconnect
        self.manager.disconnect(self.mock_websocket, self.user_identifier)
        
        # User should be removed from active connections
        self.assertNotIn(self.user_identifier, self.manager.active_connections)
    
    def test_disconnect_nonexistent_user(self):
        """Test disconnecting a user that doesn't exist"""
        # Should not raise an exception
        self.manager.disconnect(self.mock_websocket, "nonexistent_user")
        self.assertEqual(self.manager.active_connections, {})
    
    async def test_send_personal_message_success(self):
        """Test sending a message to a connected user"""
        self.mock_websocket.send_text = AsyncMock()
        self.manager.active_connections[self.user_identifier] = [self.mock_websocket]
        
        test_message = "test message"
        await self.manager.send_personal_message(test_message, self.user_identifier)
        
        self.mock_websocket.send_text.assert_called_once_with(test_message)
    
    async def test_send_personal_message_to_nonexistent_user(self):
        """Test sending a message to a user that doesn't exist"""
        # Should not raise an exception
        await self.manager.send_personal_message("test", "nonexistent_user")
        # No assertions needed, just ensuring no exception is raised
    
    async def test_send_personal_message_with_failed_connection(self):
        """Test sending a message when connection fails"""
        # Setup a websocket that will raise an exception
        self.mock_websocket.send_text = AsyncMock(side_effect=Exception("Connection failed"))
        self.manager.active_connections[self.user_identifier] = [self.mock_websocket]
        
        # Should not raise an exception, but should remove the failed connection
        await self.manager.send_personal_message("test", self.user_identifier)
        
        # Connection should be removed
        self.assertEqual(len(self.manager.active_connections[self.user_identifier]), 0)


@pytest.mark.unit
@pytest.mark.websocket
class TestWebSocketNotificationFunctions(unittest.TestCase):
    """Test the WebSocket notification functions"""
    
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        
        # Mock the connection manager
        self.manager_patcher = patch('backend.api.websocket_api.manager')
        self.mock_manager = self.manager_patcher.start()
        self.mock_manager.send_personal_message = AsyncMock()
        
        # Mock crud functions
        self.crud_patcher = patch('backend.api.websocket_api.crud')
        self.mock_crud = self.crud_patcher.start()
    
    def tearDown(self):
        self.manager_patcher.stop()
        self.crud_patcher.stop()
    
    async def test_notify_cas_deposit_update_success(self):
        """Test successful CAS deposit update notification"""
        # Setup mock deposit
        mock_deposit = MagicMock(spec=CasDeposit)
        mock_deposit.id = 1
        mock_deposit.polygon_address = "0x1234567890123456789012345678901234567890"
        mock_deposit.cascoin_deposit_address = "cas_addr_123"
        mock_deposit.status = "completed"
        mock_deposit.received_amount = 10.5
        mock_deposit.mint_tx_hash = "0xminthash"
        mock_deposit.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_deposit.updated_at.isoformat.return_value = "2023-01-01T01:00:00"
        
        self.mock_crud.get_cas_deposit_by_id.return_value = mock_deposit
        
        # Test the notification function
        await websocket_api.notify_cas_deposit_update(1, self.mock_db)
        
        # Verify crud was called
        self.mock_crud.get_cas_deposit_by_id.assert_called_once_with(self.mock_db, 1)
        
        # Verify message was sent
        self.mock_manager.send_personal_message.assert_called_once()
        call_args = self.mock_manager.send_personal_message.call_args
        message_json = call_args[0][0]
        user_address = call_args[0][1]
        
        self.assertEqual(user_address, mock_deposit.polygon_address)
        
        # Parse and verify message content
        message_data = json.loads(message_json)
        self.assertEqual(message_data["type"], "cas_deposit_update")
        self.assertEqual(message_data["data"]["id"], 1)
        self.assertEqual(message_data["data"]["status"], "completed")
    
    async def test_notify_cas_deposit_update_deposit_not_found(self):
        """Test CAS deposit update notification when deposit not found"""
        self.mock_crud.get_cas_deposit_by_id.return_value = None
        
        # Should not raise an exception
        await websocket_api.notify_cas_deposit_update(999, self.mock_db)
        
        # Manager should not be called
        self.mock_manager.send_personal_message.assert_not_called()
    
    async def test_notify_wcas_return_intention_update_success(self):
        """Test successful wCAS return intention update notification"""
        # Setup mock intention
        mock_intention = MagicMock(spec=WcasToCasReturnIntention)
        mock_intention.id = 1
        mock_intention.user_polygon_address = "0x1234567890123456789012345678901234567890"
        mock_intention.target_cascoin_address = "cas_target_addr"
        mock_intention.bridge_amount = 25.0
        mock_intention.fee_model = "direct_payment"
        mock_intention.status = "processed"
        mock_intention.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_intention.updated_at.isoformat.return_value = "2023-01-01T01:00:00"
        
        # Mock database query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_intention
        self.mock_db.query.return_value = mock_query
        
        # Test the notification function
        await websocket_api.notify_wcas_return_intention_update(1, self.mock_db)
        
        # Verify message was sent
        self.mock_manager.send_personal_message.assert_called_once()
        call_args = self.mock_manager.send_personal_message.call_args
        message_json = call_args[0][0]
        user_address = call_args[0][1]
        
        self.assertEqual(user_address, mock_intention.user_polygon_address)
        
        # Parse and verify message content
        message_data = json.loads(message_json)
        self.assertEqual(message_data["type"], "wcas_return_intention_update")
        self.assertEqual(message_data["data"]["id"], 1)
        self.assertEqual(message_data["data"]["status"], "processed")


@pytest.mark.unit
@pytest.mark.websocket
@pytest.mark.api
class TestWebSocketEndpointFunctions(unittest.TestCase):
    """Test WebSocket endpoint helper functions (not actual connections)"""
    
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        
        # Mock database models
        self.mock_cas_deposits = []
        self.mock_return_intentions = []
        
        # Mock database queries
        mock_cas_query = MagicMock()
        mock_cas_query.filter.return_value.all.return_value = self.mock_cas_deposits
        
        mock_intention_query = MagicMock()
        mock_intention_query.filter.return_value.all.return_value = self.mock_return_intentions
        
        self.mock_db.query.side_effect = lambda model: (
            mock_cas_query if model == CasDeposit else mock_intention_query
        )
    
    def test_websocket_endpoint_exists(self):
        """Test that WebSocket endpoint is properly defined"""
        from backend.api.websocket_api import router
        
        # Check that the router has WebSocket routes
        websocket_routes = [route for route in router.routes if hasattr(route, 'path') and '/ws/' in route.path]
        self.assertTrue(len(websocket_routes) > 0, "WebSocket route should be defined")
    
    @patch('backend.api.websocket_api.manager')
    async def test_send_existing_data_function(self, mock_manager):
        """Test the send_existing_data helper function"""
        mock_manager.send_personal_message = AsyncMock()
        
        # Create mock data
        mock_deposit = MagicMock()
        mock_deposit.id = 1
        mock_deposit.polygon_address = "0x123"
        mock_deposit.status = "pending"
        mock_deposit.created_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_deposit.updated_at.isoformat.return_value = "2023-01-01T00:00:00"
        mock_deposit.cascoin_deposit_address = "cas123"
        mock_deposit.received_amount = None
        mock_deposit.mint_tx_hash = None
        
        self.mock_cas_deposits = [mock_deposit]
        self.mock_return_intentions = []
        
        # Update mock to return the data
        mock_cas_query = MagicMock()
        mock_cas_query.filter.return_value.all.return_value = self.mock_cas_deposits
        mock_intention_query = MagicMock()
        mock_intention_query.filter.return_value.all.return_value = self.mock_return_intentions
        self.mock_db.query.side_effect = lambda model: (
            mock_cas_query if model == CasDeposit else mock_intention_query
        )
        
        # Test the function
        from backend.api.websocket_api import send_existing_data
        await send_existing_data("0x123", self.mock_db)
        
        # Verify that send_personal_message was called
        mock_manager.send_personal_message.assert_called()
    
    def test_connection_manager_instantiation(self):
        """Test that ConnectionManager can be instantiated"""
        from backend.api.websocket_api import ConnectionManager
        manager = ConnectionManager()
        self.assertEqual(manager.active_connections, {})


@pytest.mark.unit
@pytest.mark.websocket
@patch('backend.api.websocket_api.logger')
class TestWebSocketErrorHandling(unittest.TestCase):
    """Test WebSocket error handling and logging"""
    
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        
        # Mock the connection manager
        self.manager_patcher = patch('backend.api.websocket_api.manager')
        self.mock_manager = self.manager_patcher.start()
        self.mock_manager.send_personal_message = AsyncMock()
    
    def tearDown(self):
        self.manager_patcher.stop()
    
    async def test_notification_error_handling(self, mock_logger):
        """Test error handling in notification functions"""
        # Mock crud to raise an exception
        with patch('backend.api.websocket_api.crud.get_cas_deposit_by_id', side_effect=Exception("DB Error")):
            await websocket_api.notify_cas_deposit_update(1, self.mock_db)
            
            # Should log the error
            mock_logger.error.assert_called_once()
    
    async def test_manager_send_error_handling(self, mock_logger):
        """Test error handling when manager fails to send message"""
        self.mock_manager.send_personal_message.side_effect = Exception("Send failed")
        
        with patch('backend.api.websocket_api.crud.get_cas_deposit_by_id') as mock_get_deposit:
            mock_deposit = MagicMock()
            mock_deposit.polygon_address = "0x123"
            mock_get_deposit.return_value = mock_deposit
            
            await websocket_api.notify_cas_deposit_update(1, self.mock_db)
            
            # Should log the error
            mock_logger.error.assert_called_once()


if __name__ == '__main__':
    # Run async tests
    import sys
    if sys.version_info >= (3, 7):
        # For Python 3.7+
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy() if sys.platform == 'win32' else asyncio.DefaultEventLoopPolicy())
    
    unittest.main() 