-- Migration: Add polygon_gas_deposits table for BYO-gas flow
-- This table tracks MATIC payments for gas fees in the bridge system

CREATE TABLE IF NOT EXISTS polygon_gas_deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cas_deposit_id INTEGER NOT NULL,
    polygon_gas_address VARCHAR(42) UNIQUE NOT NULL,
    required_matic DECIMAL(78,18) NOT NULL,
    received_matic DECIMAL(78,18) DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    hd_index INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (cas_deposit_id) REFERENCES cas_deposits(id),
    
    CONSTRAINT check_status CHECK (status IN ('pending', 'funded', 'spent', 'expired')),
    CONSTRAINT check_required_matic_positive CHECK (required_matic > 0),
    CONSTRAINT check_received_matic_non_negative CHECK (received_matic >= 0),
    CONSTRAINT check_hd_index_non_negative CHECK (hd_index >= 0)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_polygon_gas_deposits_cas_deposit_id ON polygon_gas_deposits(cas_deposit_id);
CREATE INDEX IF NOT EXISTS idx_polygon_gas_deposits_status ON polygon_gas_deposits(status);
CREATE INDEX IF NOT EXISTS idx_polygon_gas_deposits_address ON polygon_gas_deposits(polygon_gas_address);
CREATE INDEX IF NOT EXISTS idx_polygon_gas_deposits_created_at ON polygon_gas_deposits(created_at);

-- Add a trigger to update the updated_at column
CREATE TRIGGER IF NOT EXISTS update_polygon_gas_deposits_updated_at
    AFTER UPDATE ON polygon_gas_deposits
    FOR EACH ROW
BEGIN
    UPDATE polygon_gas_deposits 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END; 