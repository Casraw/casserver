class BridgeRealtimeClient {
    constructor(userAddress) {
        this.userAddress = userAddress;
        this.socket = null;
        this.reconnectInterval = 5000; // 5 seconds
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.eventHandlers = {};
        
        // Bind methods to preserve 'this' context
        this.connect = this.connect.bind(this);
        this.disconnect = this.disconnect.bind(this);
        this.handleMessage = this.handleMessage.bind(this);
        this.handleClose = this.handleClose.bind(this);
        this.handleError = this.handleError.bind(this);
    }
    
    connect() {
        if (this.isConnecting || (this.socket && this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }
        
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            return;
        }
        
        this.isConnecting = true;
        
        try {
            // Use ws:// for development, wss:// for production
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/ws/${encodeURIComponent(this.userAddress)}`;
            
            console.log('Connecting to WebSocket:', wsUrl);
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this.triggerEvent('connected');
                
                // Send a ping to confirm connection
                this.send({type: 'ping'});
            };
            
            this.socket.onmessage = this.handleMessage;
            this.socket.onclose = this.handleClose;
            this.socket.onerror = this.handleError;
            
        } catch (error) {
            console.error('Error creating WebSocket connection:', error);
            this.isConnecting = false;
            this.scheduleReconnect();
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
    }
    
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('Received WebSocket message:', data);
            
            switch (data.type) {
                case 'pong':
                    // Handle ping/pong for keepalive
                    break;
                case 'cas_deposit_update':
                    this.triggerEvent('casDepositUpdate', data.data);
                    break;
                case 'wcas_return_intention_update':
                    this.triggerEvent('wcasReturnIntentionUpdate', data.data);
                    break;
                case 'polygon_transaction_update':
                    this.triggerEvent('polygonTransactionUpdate', data.data);
                    break;
                case 'error':
                    console.error('WebSocket error:', data.message);
                    this.triggerEvent('error', data.message);
                    break;
                default:
                    console.log('Unknown message type:', data.type);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }
    
    handleClose(event) {
        console.log('WebSocket closed:', event.code, event.reason);
        this.socket = null;
        this.isConnecting = false;
        this.triggerEvent('disconnected');
        
        // Attempt to reconnect unless it was a clean close
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
        }
    }
    
    handleError(error) {
        console.error('WebSocket error:', error);
        this.isConnecting = false;
        this.triggerEvent('error', error);
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnect attempts reached');
            this.triggerEvent('maxReconnectAttemptsReached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectInterval * this.reconnectAttempts;
        
        console.log(`Reconnecting in ${delay/1000} seconds... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.triggerEvent('reconnecting', {attempt: this.reconnectAttempts, delay: delay});
        
        setTimeout(this.connect, delay);
    }
    
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('Cannot send message: WebSocket not connected');
        }
    }
    
    requestStatusUpdate() {
        this.send({type: 'request_status_update'});
    }
    
    // Event handling methods
    on(event, handler) {
        if (!this.eventHandlers[event]) {
            this.eventHandlers[event] = [];
        }
        this.eventHandlers[event].push(handler);
    }
    
    off(event, handler) {
        if (this.eventHandlers[event]) {
            const index = this.eventHandlers[event].indexOf(handler);
            if (index > -1) {
                this.eventHandlers[event].splice(index, 1);
            }
        }
    }
    
    triggerEvent(event, data) {
        if (this.eventHandlers[event]) {
            this.eventHandlers[event].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in event handler for ${event}:`, error);
                }
            });
        }
    }
}

// Utility functions for updating the UI
class BridgeUIUpdater {
    constructor() {
        this.statusColors = {
            'pending': '#ffc107',
            'pending_deposit': '#ffc107',
            'pending_confirmation': '#17a2b8',
            'confirmed': '#28a745',
            'completed': '#28a745',
            'failed': '#dc3545',
            'expired': '#6c757d'
        };
        
        this.statusLabels = {
            'pending': 'Pending',
            'pending_deposit': 'Pending Deposit',
            'pending_confirmation': 'Confirming',
            'deposit_detected': 'Deposit Detected',
            'confirmed': 'Confirmed',
            'completed': 'Completed',
            'processed': 'Processed',
            'failed': 'Failed',
            'expired': 'Expired'
        };
    }
    
    updateCasDepositStatus(deposit) {
        const responseArea = document.getElementById('responseArea');
        const responseText = document.getElementById('responseText');
        
        if (!responseArea || !responseText) return;
        
        const statusColor = this.statusColors[deposit.status] || '#6c757d';
        const statusLabel = this.statusLabels[deposit.status] || deposit.status;
        
        let html = `
            <div style="border-left: 4px solid ${statusColor}; padding-left: 15px; margin: 10px 0;">
                <h5 style="color: ${statusColor}; margin: 0 0 10px 0;">
                    🔄 Bridge Status: ${statusLabel}
                </h5>
                <div><strong>Deposit ID:</strong> ${deposit.id}</div>
                <div><strong>Cascoin Deposit Address:</strong> 
                    <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">${deposit.cascoin_deposit_address}</code>
                </div>
                <div><strong>Your Polygon Address:</strong> 
                    <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">${deposit.polygon_address}</code>
                </div>
        `;
        
        if (deposit.received_amount) {
            html += `<div><strong>Received Amount:</strong> ${deposit.received_amount} CAS</div>`;
        }
        
        if (deposit.mint_tx_hash) {
            html += `<div><strong>Mint Transaction:</strong> 
                <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">${deposit.mint_tx_hash}</code>
            </div>`;
        }
        
        html += `
                <div><strong>Created:</strong> ${new Date(deposit.created_at).toLocaleString()}</div>
                <div><strong>Last Updated:</strong> ${new Date(deposit.updated_at).toLocaleString()}</div>
            </div>
        `;
        
        // Add instructions based on status
        if (deposit.status === 'pending') {
            html += `
                <div class="info" style="background: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    💡 <strong>Next Step:</strong> Send CAS to the deposit address above to start the bridge process.
                </div>
            `;
        } else if (deposit.status === 'pending_confirmation') {
            html += `
                <div class="info" style="background: #e8f5e8; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    ⏳ <strong>Processing:</strong> Your deposit has been detected and is being confirmed on the Cascoin network.
                </div>
            `;
        } else if (deposit.status === 'completed') {
            html += `
                <div class="success">
                    ✅ <strong>Complete!</strong> Your wCAS tokens have been minted and sent to your Polygon address.
                </div>
            `;
        }
        
        responseText.innerHTML = html;
        responseArea.style.display = 'block';
    }
    
    updateWcasReturnIntentionStatus(intention) {
        const responseArea = document.getElementById('responseArea');
        const responseText = document.getElementById('responseText');
        
        if (!responseArea || !responseText) return;
        
        const statusColor = this.statusColors[intention.status] || '#6c757d';
        const statusLabel = this.statusLabels[intention.status] || intention.status;
        
        let html = `
            <div style="border-left: 4px solid ${statusColor}; padding-left: 15px; margin: 10px 0;">
                <h5 style="color: ${statusColor}; margin: 0 0 10px 0;">
                    🔄 Bridge Status: ${statusLabel}
                </h5>
                <div><strong>Return Intention ID:</strong> ${intention.id}</div>
                <div><strong>From Polygon Address:</strong> 
                    <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">${intention.user_polygon_address}</code>
                </div>
                <div><strong>To Cascoin Address:</strong> 
                    <code style="background: #f8f9fa; padding: 2px 6px; border-radius: 3px;">${intention.target_cascoin_address}</code>
                </div>
                <div><strong>Bridge Amount:</strong> ${intention.bridge_amount} wCAS</div>
                <div><strong>Fee Model:</strong> ${intention.fee_model}</div>
                <div><strong>Created:</strong> ${new Date(intention.created_at).toLocaleString()}</div>
                <div><strong>Last Updated:</strong> ${new Date(intention.updated_at).toLocaleString()}</div>
            </div>
        `;
        
        // Add instructions based on status
        if (intention.status === 'pending_deposit') {
            html += `
                <div class="info" style="background: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    💡 <strong>Next Step:</strong> Send ${intention.bridge_amount} wCAS from your Polygon address to the bridge contract to complete the return process.
                </div>
            `;
        } else if (intention.status === 'deposit_detected') {
            html += `
                <div class="info" style="background: #e8f5e8; padding: 10px; border-radius: 4px; margin: 10px 0;">
                    ⏳ <strong>Processing:</strong> Your wCAS deposit has been detected and CAS is being sent to your Cascoin address.
                </div>
            `;
        } else if (intention.status === 'processed') {
            html += `
                <div class="success">
                    ✅ <strong>Complete!</strong> Your CAS has been sent to your Cascoin address.
                </div>
            `;
        }
        
        responseText.innerHTML = html;
        responseArea.style.display = 'block';
    }
    
    showConnectionStatus(isConnected, message = '') {
        let statusElement = document.getElementById('connectionStatus');
        
        if (!statusElement) {
            statusElement = document.createElement('div');
            statusElement.id = 'connectionStatus';
            statusElement.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                z-index: 1000;
                transition: all 0.3s ease;
            `;
            document.body.appendChild(statusElement);
        }
        
        if (isConnected) {
            statusElement.style.backgroundColor = '#d4edda';
            statusElement.style.color = '#155724';
            statusElement.style.border = '1px solid #c3e6cb';
            statusElement.innerHTML = '🟢 Real-time updates active';
        } else {
            statusElement.style.backgroundColor = '#f8d7da';
            statusElement.style.color = '#721c24';
            statusElement.style.border = '1px solid #f5c6cb';
            statusElement.innerHTML = `🔴 ${message || 'Real-time updates disconnected'}`;
        }
    }
}

// Global utility function to initialize real-time updates
window.initializeBridgeRealtime = function(userAddress) {
    if (!userAddress || userAddress.length < 10) {
        console.warn('Invalid user address provided for real-time updates');
        return null;
    }
    
    const client = new BridgeRealtimeClient(userAddress);
    const uiUpdater = new BridgeUIUpdater();
    
    // Set up event handlers
    client.on('connected', () => {
        uiUpdater.showConnectionStatus(true);
    });
    
    client.on('disconnected', () => {
        uiUpdater.showConnectionStatus(false, 'Disconnected');
    });
    
    client.on('reconnecting', (data) => {
        uiUpdater.showConnectionStatus(false, `Reconnecting... (${data.attempt}/${client.maxReconnectAttempts})`);
    });
    
    client.on('casDepositUpdate', (deposit) => {
        uiUpdater.updateCasDepositStatus(deposit);
    });
    
    client.on('wcasReturnIntentionUpdate', (intention) => {
        uiUpdater.updateWcasReturnIntentionStatus(intention);
    });
    
    client.on('error', (error) => {
        console.error('Real-time client error:', error);
    });
    
    // Connect to WebSocket
    client.connect();
    
    return client;
}; 