-- PostgreSQL Initialization Script for Cascoin-Polygon Bridge
-- This script runs when the PostgreSQL container starts for the first time

-- Create database if not exists (usually not needed as it's created by POSTGRES_DB)
-- CREATE DATABASE IF NOT EXISTS cascoin_bridge;

-- Set timezone
SET timezone = 'UTC';

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The 'bridge_user' is created automatically by the postgres container
-- via the POSTGRES_USER environment variable.
-- No need to create the 'postgres' user if the application is configured
-- to use 'bridge_user'.

-- Grant necessary permissions to bridge_user
-- (The user is already created by the PostgreSQL container with POSTGRES_USER)

-- Optional: Create additional indexes for performance
-- These will be created by SQLAlchemy models, but you can add custom ones here

-- Log the initialization
DO $$
BEGIN
    RAISE NOTICE 'Cascoin-Polygon Bridge PostgreSQL database initialized successfully';
END
$$; 