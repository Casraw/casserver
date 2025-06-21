-- Migration to add confirmation tracking columns to existing tables
-- Run this after database initialization

-- Add confirmation tracking to cas_deposits table
ALTER TABLE cas_deposits ADD COLUMN current_confirmations INTEGER DEFAULT 0;
ALTER TABLE cas_deposits ADD COLUMN required_confirmations INTEGER DEFAULT 12;
ALTER TABLE cas_deposits ADD COLUMN deposit_tx_hash VARCHAR(255);

-- Add confirmation tracking to polygon_transactions table
ALTER TABLE polygon_transactions ADD COLUMN current_confirmations INTEGER DEFAULT 0;
ALTER TABLE polygon_transactions ADD COLUMN required_confirmations INTEGER DEFAULT 12;

-- Update existing records to have default values
UPDATE cas_deposits SET current_confirmations = 0 WHERE current_confirmations IS NULL;
UPDATE cas_deposits SET required_confirmations = 12 WHERE required_confirmations IS NULL;
UPDATE polygon_transactions SET current_confirmations = 0 WHERE current_confirmations IS NULL;
UPDATE polygon_transactions SET required_confirmations = 12 WHERE required_confirmations IS NULL; 