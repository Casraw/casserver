import asyncio
import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class WebSocketNotificationService:
    """Service to handle sending WebSocket notifications for database updates"""
    
    def __init__(self):
        self._loop = None
        
    def get_event_loop(self):
        """Get or create event loop for async operations"""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                # Create new event loop if none exists
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def notify_cas_deposit_update(self, deposit_id: int, db: Session):
        """Schedule a WebSocket notification for CAS deposit update"""
        try:
            loop = self.get_event_loop()
            if loop.is_running():
                # If loop is already running, schedule as a task
                asyncio.create_task(self._notify_cas_deposit_update_async(deposit_id, db))
            else:
                # If loop is not running, run the coroutine
                loop.run_until_complete(self._notify_cas_deposit_update_async(deposit_id, db))
        except Exception as e:
            logger.error(f"Error scheduling CAS deposit notification: {e}")
    
    def notify_wcas_return_intention_update(self, intention_id: int, db: Session):
        """Schedule a WebSocket notification for wCAS return intention update"""
        try:
            loop = self.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._notify_wcas_return_intention_update_async(intention_id, db))
            else:
                loop.run_until_complete(self._notify_wcas_return_intention_update_async(intention_id, db))
        except Exception as e:
            logger.error(f"Error scheduling wCAS return intention notification: {e}")
    
    def notify_polygon_transaction_update(self, tx_id: int, db: Session):
        """Schedule a WebSocket notification for Polygon transaction update"""
        try:
            loop = self.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._notify_polygon_transaction_update_async(tx_id, db))
            else:
                loop.run_until_complete(self._notify_polygon_transaction_update_async(tx_id, db))
        except Exception as e:
            logger.error(f"Error scheduling Polygon transaction notification: {e}")
    
    async def _notify_cas_deposit_update_async(self, deposit_id: int, db: Session):
        """Async method to send CAS deposit update notification"""
        try:
            # Import here to avoid circular imports
            from backend.api.websocket_api import notify_cas_deposit_update
            await notify_cas_deposit_update(deposit_id, db)
        except Exception as e:
            logger.error(f"Error sending CAS deposit update notification: {e}")
    
    async def _notify_wcas_return_intention_update_async(self, intention_id: int, db: Session):
        """Async method to send wCAS return intention update notification"""
        try:
            from backend.api.websocket_api import notify_wcas_return_intention_update
            await notify_wcas_return_intention_update(intention_id, db)
        except Exception as e:
            logger.error(f"Error sending wCAS return intention update notification: {e}")
    
    async def _notify_polygon_transaction_update_async(self, tx_id: int, db: Session):
        """Async method to send Polygon transaction update notification"""
        try:
            from backend.api.websocket_api import notify_polygon_transaction_update
            await notify_polygon_transaction_update(tx_id, db)
        except Exception as e:
            logger.error(f"Error sending Polygon transaction update notification: {e}")

# Global instance
websocket_notifier = WebSocketNotificationService() 