import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
import pytest

from backend.services.websocket_notifier import WebSocketNotificationService, websocket_notifier


@pytest.mark.unit
@pytest.mark.websocket
@pytest.mark.services
class TestWebSocketNotificationService(unittest.TestCase):
    """Test the WebSocketNotificationService class"""
    
    def setUp(self):
        self.service = WebSocketNotificationService()
        self.mock_db = MagicMock(spec=Session)
    
    def test_init(self):
        """Test service initialization"""
        self.assertIsNone(self.service._loop)
    
    def test_get_event_loop_creates_new_loop(self):
        """Test that get_event_loop creates a new loop when none exists"""
        # Reset the loop
        self.service._loop = None
        
        with patch('asyncio.get_event_loop', side_effect=RuntimeError("No loop")):
            with patch('asyncio.new_event_loop') as mock_new_loop:
                with patch('asyncio.set_event_loop') as mock_set_loop:
                    mock_loop = MagicMock()
                    mock_new_loop.return_value = mock_loop
                    
                    result = self.service.get_event_loop()
                    
                    mock_new_loop.assert_called_once()
                    mock_set_loop.assert_called_once_with(mock_loop)
                    self.assertEqual(result, mock_loop)
    
    def test_get_event_loop_returns_existing(self):
        """Test that get_event_loop returns existing loop"""
        with patch('asyncio.get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            result = self.service.get_event_loop()
            
            mock_get_loop.assert_called_once()
            self.assertEqual(result, mock_loop)
    
    @patch('asyncio.create_task')
    def test_notify_cas_deposit_update_running_loop(self, mock_create_task):
        """Test CAS deposit notification when loop is running"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            self.service.notify_cas_deposit_update(1, self.mock_db)
            
            mock_create_task.assert_called_once()
    
    def test_notify_cas_deposit_update_not_running_loop(self):
        """Test CAS deposit notification when loop is not running"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            with patch.object(self.service, '_notify_cas_deposit_update_async') as mock_async:
                self.service.notify_cas_deposit_update(1, self.mock_db)
                
                # Verify that run_until_complete was called with the coroutine
                mock_loop.run_until_complete.assert_called_once()
                # Verify the mock was called with correct arguments
                mock_async.assert_called_once_with(1, self.mock_db)
    
    def test_notify_cas_deposit_update_error_handling(self):
        """Test error handling in CAS deposit notification"""
        with patch.object(self.service, 'get_event_loop', side_effect=Exception("Loop error")):
            with patch('backend.services.websocket_notifier.logger') as mock_logger:
                # Should not raise an exception
                self.service.notify_cas_deposit_update(1, self.mock_db)
                
                mock_logger.error.assert_called_once()
    
    @patch('asyncio.create_task')
    def test_notify_wcas_return_intention_update_running_loop(self, mock_create_task):
        """Test wCAS return intention notification when loop is running"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            self.service.notify_wcas_return_intention_update(1, self.mock_db)
            
            mock_create_task.assert_called_once()
    
    def test_notify_wcas_return_intention_update_not_running_loop(self):
        """Test wCAS return intention notification when loop is not running"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            with patch.object(self.service, '_notify_wcas_return_intention_update_async') as mock_async:
                self.service.notify_wcas_return_intention_update(1, self.mock_db)
                
                # Verify that run_until_complete was called with the coroutine
                mock_loop.run_until_complete.assert_called_once()
                # Verify the mock was called with correct arguments
                mock_async.assert_called_once_with(1, self.mock_db)
    
    @patch('asyncio.create_task')
    def test_notify_polygon_transaction_update_running_loop(self, mock_create_task):
        """Test Polygon transaction notification when loop is running"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            self.service.notify_polygon_transaction_update(1, self.mock_db)
            
            mock_create_task.assert_called_once()
    
    async def test_notify_cas_deposit_update_async_success(self):
        """Test async CAS deposit notification success"""
        with patch('backend.api.websocket_api.notify_cas_deposit_update') as mock_notify:
            mock_notify.return_value = asyncio.coroutine(lambda: None)()
            
            await self.service._notify_cas_deposit_update_async(1, self.mock_db)
            
            mock_notify.assert_called_once_with(1, self.mock_db)
    
    async def test_notify_cas_deposit_update_async_error(self):
        """Test async CAS deposit notification error handling"""
        with patch('backend.api.websocket_api.notify_cas_deposit_update', side_effect=Exception("Notify error")):
            with patch('backend.services.websocket_notifier.logger') as mock_logger:
                await self.service._notify_cas_deposit_update_async(1, self.mock_db)
                
                mock_logger.error.assert_called_once()
    
    async def test_notify_wcas_return_intention_update_async_success(self):
        """Test async wCAS return intention notification success"""
        with patch('backend.api.websocket_api.notify_wcas_return_intention_update') as mock_notify:
            mock_notify.return_value = asyncio.coroutine(lambda: None)()
            
            await self.service._notify_wcas_return_intention_update_async(1, self.mock_db)
            
            mock_notify.assert_called_once_with(1, self.mock_db)
    
    async def test_notify_wcas_return_intention_update_async_error(self):
        """Test async wCAS return intention notification error handling"""
        with patch('backend.api.websocket_api.notify_wcas_return_intention_update', side_effect=Exception("Notify error")):
            with patch('backend.services.websocket_notifier.logger') as mock_logger:
                await self.service._notify_wcas_return_intention_update_async(1, self.mock_db)
                
                mock_logger.error.assert_called_once()
    
    async def test_notify_polygon_transaction_update_async_success(self):
        """Test async Polygon transaction notification success"""
        with patch('backend.api.websocket_api.notify_polygon_transaction_update') as mock_notify:
            mock_notify.return_value = asyncio.coroutine(lambda: None)()
            
            await self.service._notify_polygon_transaction_update_async(1, self.mock_db)
            
            mock_notify.assert_called_once_with(1, self.mock_db)
    
    async def test_notify_polygon_transaction_update_async_error(self):
        """Test async Polygon transaction notification error handling"""
        with patch('backend.api.websocket_api.notify_polygon_transaction_update', side_effect=Exception("Notify error")):
            with patch('backend.services.websocket_notifier.logger') as mock_logger:
                await self.service._notify_polygon_transaction_update_async(1, self.mock_db)
                
                mock_logger.error.assert_called_once()


@pytest.mark.unit
@pytest.mark.websocket
@pytest.mark.services
class TestGlobalWebSocketNotifier(unittest.TestCase):
    """Test the global websocket_notifier instance"""
    
    def test_global_instance_exists(self):
        """Test that global instance is properly initialized"""
        self.assertIsInstance(websocket_notifier, WebSocketNotificationService)
    
    def test_global_instance_methods_callable(self):
        """Test that global instance methods are callable"""
        mock_db = MagicMock(spec=Session)
        
        with patch.object(websocket_notifier, 'get_event_loop') as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = False
            mock_loop.run_until_complete = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            with patch.object(websocket_notifier, '_notify_cas_deposit_update_async'):
                # Should not raise an exception
                websocket_notifier.notify_cas_deposit_update(1, mock_db)
                
                mock_get_loop.assert_called_once()
                mock_loop.run_until_complete.assert_called_once()


@pytest.mark.integration
@pytest.mark.websocket
@pytest.mark.services
class TestWebSocketNotifierIntegration(unittest.TestCase):
    """Integration tests for WebSocket notifier with mocked dependencies"""
    
    def setUp(self):
        self.mock_db = MagicMock(spec=Session)
        self.service = WebSocketNotificationService()
    
    def test_full_notification_cycle_cas_deposit(self):
        """Test full notification cycle for CAS deposit"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            with patch('backend.api.websocket_api.notify_cas_deposit_update') as mock_notify:
                async def mock_async_notify(deposit_id, db):
                    self.assertEqual(deposit_id, 1)
                    self.assertEqual(db, self.mock_db)
                
                mock_notify.side_effect = mock_async_notify
                
                # This should execute the full cycle
                self.service.notify_cas_deposit_update(1, self.mock_db)
                
                # Verify the async function was scheduled
                mock_loop.run_until_complete.assert_called_once()
    
    def test_full_notification_cycle_wcas_return_intention(self):
        """Test full notification cycle for wCAS return intention"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            with patch('backend.api.websocket_api.notify_wcas_return_intention_update') as mock_notify:
                async def mock_async_notify(intention_id, db):
                    self.assertEqual(intention_id, 1)
                    self.assertEqual(db, self.mock_db)
                
                mock_notify.side_effect = mock_async_notify
                
                # This should execute the full cycle
                self.service.notify_wcas_return_intention_update(1, self.mock_db)
                
                # Verify the async function was scheduled
                mock_loop.run_until_complete.assert_called_once()
    
    def test_full_notification_cycle_polygon_transaction(self):
        """Test full notification cycle for Polygon transaction"""
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = False
        
        with patch.object(self.service, 'get_event_loop', return_value=mock_loop):
            with patch('backend.api.websocket_api.notify_polygon_transaction_update') as mock_notify:
                async def mock_async_notify(tx_id, db):
                    self.assertEqual(tx_id, 1)
                    self.assertEqual(db, self.mock_db)
                
                mock_notify.side_effect = mock_async_notify
                
                # This should execute the full cycle
                self.service.notify_polygon_transaction_update(1, self.mock_db)
                
                # Verify the async function was scheduled
                mock_loop.run_until_complete.assert_called_once()


if __name__ == '__main__':
    unittest.main() 