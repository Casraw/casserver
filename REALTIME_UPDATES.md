# Real-time Bridge Updates

This document explains the real-time update system that has been added to your Cascoin-Polygon bridge interface.

## What Was Added

### Backend Components

1. **WebSocket API** (`backend/api/websocket_api.py`)
   - WebSocket endpoint at `/api/ws/{user_address}`
   - Connection manager for handling multiple client connections
   - Real-time status broadcasting functions

2. **WebSocket Notifier Service** (`backend/services/websocket_notifier.py`)
   - Service to handle sending notifications when database records are updated
   - Automatically called from CRUD operations

3. **Enhanced CRUD Operations** (`backend/crud.py`)
   - All update functions now automatically send WebSocket notifications
   - Covers CasDeposit, WcasToCasReturnIntention, and PolygonTransaction updates

### Frontend Components

1. **Real-time Client** (`frontend/js/realtime.js`)
   - `BridgeRealtimeClient` class for WebSocket connections
   - `BridgeUIUpdater` class for updating the user interface
   - Automatic reconnection handling
   - Connection status indicators

2. **Enhanced Bridge Pages**
   - Both `cas_to_poly.html` and `poly_to_cas.html` now include real-time functionality
   - Automatic status updates without page refresh
   - Live connection status indicator

## How It Works

### For CAS → Polygon Bridge:

1. User enters their Polygon address and bridge amount
2. User clicks "Get Cascoin Deposit Address"
3. **Real-time updates start automatically** using the user's Polygon address
4. Backend creates a CasDeposit record with status "pending"
5. User sends CAS to the provided deposit address
6. When your watcher detects the deposit:
   - Status changes to "pending_confirmation" → **User sees update instantly**
   - Amount received is recorded → **User sees update instantly**
   - Status changes to "completed" when wCAS is minted → **User sees update instantly**

### For Polygon → CAS Bridge:

1. User enters their Polygon and Cascoin addresses with bridge amount
2. User clicks "Get wCAS Deposit Address"
3. **Real-time updates start automatically** using the user's Polygon address
4. Backend creates a WcasToCasReturnIntention with status "pending_deposit"
5. User sends wCAS to the bridge contract
6. When your watcher detects the wCAS deposit:
   - Status changes to "deposit_detected" → **User sees update instantly**
   - Status changes to "processed" when CAS is sent → **User sees update instantly**

## Visual Indicators

### Connection Status
- 🟢 "Real-time updates active" - Connected and receiving updates
- 🔴 "Real-time updates disconnected" - Connection lost
- 🔴 "Reconnecting... (1/10)" - Attempting to reconnect

### Status Updates
- **Pending** (Yellow) - Waiting for user action
- **Pending Confirmation** (Blue) - Processing transaction
- **Completed/Processed** (Green) - Successfully finished
- **Failed** (Red) - Something went wrong

## Status Flow Examples

### CAS to Polygon:
```
Pending → Pending Confirmation → Completed
  ↓            ↓                    ↓
Send CAS   Deposit detected    wCAS minted
```

### Polygon to CAS:
```
Pending Deposit → Deposit Detected → Processed
      ↓                ↓               ↓
   Send wCAS      wCAS received    CAS sent
```

## Technical Details

### WebSocket Connection
- Connects to: `ws://localhost:8000/api/ws/{polygon_address}`
- Automatically reconnects on connection loss (up to 10 attempts)
- Sends ping/pong messages to keep connection alive

### Message Types
- `cas_deposit_update` - CAS deposit status changes
- `wcas_return_intention_update` - wCAS return intention changes
- `polygon_transaction_update` - Polygon transaction updates

### Automatic Integration
The system automatically triggers when:
- `update_cas_deposit_status_and_mint_hash()` is called
- `update_wcas_return_intention_status()` is called
- `update_polygon_transaction_status_and_cas_hash()` is called

## Browser Compatibility
- Modern browsers with WebSocket support
- Automatic fallback to HTTP polling (not implemented yet, but can be added)

## Security Considerations
- WebSocket connections are isolated by user address
- No sensitive data is transmitted over WebSocket
- Connection automatically closes when user leaves the page

## Troubleshooting

### If real-time updates aren't working:
1. Check browser console for WebSocket errors
2. Ensure your server supports WebSocket connections
3. Check if WebSocket endpoint is accessible at `/api/ws/{address}`
4. Verify the user address format (must be valid Ethereum address)

### Common Issues:
- **"Invalid user address"** - Make sure address starts with 0x and is 42 characters
- **Connection keeps dropping** - Check server logs for WebSocket errors
- **Updates not showing** - Verify CRUD operations are calling notification functions

## Testing Real-time Updates

You can test the system by:
1. Opening the bridge interface
2. Creating a bridge request
3. Manually updating the database record status
4. The UI should update automatically without page refresh

Example SQL to test:
```sql
-- Update a CAS deposit status
UPDATE cas_deposits SET status = 'completed' WHERE id = 1;
```

The real-time system will detect this change and push an update to connected clients. 