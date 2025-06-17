from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import crud
from database.models import CasDeposit, WcasToCasReturnIntention, PolygonTransaction
from typing import Dict, List
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, user_identifier: str):
        await websocket.accept()
        if user_identifier not in self.active_connections:
            self.active_connections[user_identifier] = []
        self.active_connections[user_identifier].append(websocket)
        logger.info(f"WebSocket connected for user: {user_identifier}")
        
    def disconnect(self, websocket: WebSocket, user_identifier: str):
        if user_identifier in self.active_connections:
            if websocket in self.active_connections[user_identifier]:
                self.active_connections[user_identifier].remove(websocket)
            if not self.active_connections[user_identifier]:
                del self.active_connections[user_identifier]
        logger.info(f"WebSocket disconnected for user: {user_identifier}")
        
    async def send_personal_message(self, message: str, user_identifier: str):
        if user_identifier in self.active_connections:
            connections_to_remove = []
            for connection in self.active_connections[user_identifier][:]:  # Create a copy of the list
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message to {user_identifier}: {e}")
                    connections_to_remove.append(connection)
            
            # Remove dead connections
            for connection in connections_to_remove:
                if connection in self.active_connections[user_identifier]:
                    self.active_connections[user_identifier].remove(connection)
                
    async def broadcast_to_all(self, message: str):
        for user_identifier, connections in list(self.active_connections.items()):
            connections_to_remove = []
            for connection in connections[:]:  # Create a copy of the list
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {user_identifier}: {e}")
                    connections_to_remove.append(connection)
            
            # Remove dead connections
            for connection in connections_to_remove:
                if connection in connections:
                    connections.remove(connection)

manager = ConnectionManager()

@router.websocket("/ws/{user_identifier}")
async def websocket_endpoint(websocket: WebSocket, user_identifier: str, db: Session = Depends(get_db)):
    await manager.connect(websocket, user_identifier)
    
    try:
        # Send initial status for the user
        await send_initial_status(websocket, user_identifier, db)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle different message types
                if message_data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message_data.get("type") == "request_status_update":
                    await send_status_update(websocket, user_identifier, db)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
            except asyncio.TimeoutError:
                # Ping to keep connection alive
                await websocket.send_text(json.dumps({"type": "ping"}))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_identifier)
    except Exception as e:
        logger.error(f"WebSocket error for {user_identifier}: {e}")
        manager.disconnect(websocket, user_identifier)

async def send_initial_status(websocket: WebSocket, user_identifier: str, db: Session):
    """Send initial status for all relevant records for this user"""
    try:
        # Get CAS deposits for this user (assuming user_identifier is polygon_address)
        cas_deposits = db.query(CasDeposit).filter(
            CasDeposit.polygon_address == user_identifier
        ).all()
        
        for deposit in cas_deposits:
            await websocket.send_text(json.dumps({
                "type": "cas_deposit_update",
                "data": {
                    "id": deposit.id,
                    "polygon_address": deposit.polygon_address,
                    "cascoin_deposit_address": deposit.cascoin_deposit_address,
                    "status": deposit.status,
                    "received_amount": deposit.received_amount,
                    "mint_tx_hash": deposit.mint_tx_hash,
                    "created_at": deposit.created_at.isoformat() if deposit.created_at else None,
                    "updated_at": deposit.updated_at.isoformat() if deposit.updated_at else None
                }
            }))
        
        # Get wCAS to CAS return intentions
        return_intentions = db.query(WcasToCasReturnIntention).filter(
            WcasToCasReturnIntention.user_polygon_address == user_identifier
        ).all()
        
        for intention in return_intentions:
            await websocket.send_text(json.dumps({
                "type": "wcas_return_intention_update",
                "data": {
                    "id": intention.id,
                    "user_polygon_address": intention.user_polygon_address,
                    "target_cascoin_address": intention.target_cascoin_address,
                    "bridge_amount": intention.bridge_amount,
                    "fee_model": intention.fee_model,
                    "status": intention.status,
                    "created_at": intention.created_at.isoformat() if intention.created_at else None,
                    "updated_at": intention.updated_at.isoformat() if intention.updated_at else None
                }
            }))
            
    except Exception as e:
        logger.error(f"Error sending initial status to {user_identifier}: {e}")

async def send_status_update(websocket: WebSocket, user_identifier: str, db: Session):
    """Send current status update for this user"""
    await send_initial_status(websocket, user_identifier, db)

# Functions to notify clients of updates (to be called from watchers/services)
async def notify_cas_deposit_update(deposit_id: int, db: Session):
    """Notify clients about CAS deposit status changes"""
    try:
        deposit = crud.get_cas_deposit_by_id(db, deposit_id)
        if deposit:
            message = json.dumps({
                "type": "cas_deposit_update",
                "data": {
                    "id": deposit.id,
                    "polygon_address": deposit.polygon_address,
                    "cascoin_deposit_address": deposit.cascoin_deposit_address,
                    "status": deposit.status,
                    "received_amount": deposit.received_amount,
                    "mint_tx_hash": deposit.mint_tx_hash,
                    "created_at": deposit.created_at.isoformat() if deposit.created_at else None,
                    "updated_at": deposit.updated_at.isoformat() if deposit.updated_at else None
                }
            })
            await manager.send_personal_message(message, deposit.polygon_address)
    except Exception as e:
        logger.error(f"Error notifying CAS deposit update: {e}")

async def notify_wcas_return_intention_update(intention_id: int, db: Session):
    """Notify clients about wCAS return intention status changes"""
    try:
        intention = db.query(WcasToCasReturnIntention).filter(
            WcasToCasReturnIntention.id == intention_id
        ).first()
        
        if intention:
            message = json.dumps({
                "type": "wcas_return_intention_update",
                "data": {
                    "id": intention.id,
                    "user_polygon_address": intention.user_polygon_address,
                    "target_cascoin_address": intention.target_cascoin_address,
                    "bridge_amount": intention.bridge_amount,
                    "fee_model": intention.fee_model,
                    "status": intention.status,
                    "created_at": intention.created_at.isoformat() if intention.created_at else None,
                    "updated_at": intention.updated_at.isoformat() if intention.updated_at else None
                }
            })
            await manager.send_personal_message(message, intention.user_polygon_address)
    except Exception as e:
        logger.error(f"Error notifying wCAS return intention update: {e}")

async def notify_polygon_transaction_update(tx_id: int, db: Session):
    """Notify clients about Polygon transaction status changes"""
    try:
        poly_tx = crud.get_polygon_transaction_by_id(db, tx_id)
        if poly_tx:
            message = json.dumps({
                "type": "polygon_transaction_update",
                "data": {
                    "id": poly_tx.id,
                    "user_cascoin_address_request": poly_tx.user_cascoin_address_request,
                    "from_address": poly_tx.from_address,
                    "to_address": poly_tx.to_address,
                    "amount": poly_tx.amount,
                    "polygon_tx_hash": poly_tx.polygon_tx_hash,
                    "status": poly_tx.status,
                    "cas_release_tx_hash": poly_tx.cas_release_tx_hash,
                    "created_at": poly_tx.created_at.isoformat() if poly_tx.created_at else None,
                    "updated_at": poly_tx.updated_at.isoformat() if poly_tx.updated_at else None
                }
            })
            await manager.send_personal_message(message, poly_tx.from_address)
    except Exception as e:
        logger.error(f"Error notifying Polygon transaction update: {e}") 