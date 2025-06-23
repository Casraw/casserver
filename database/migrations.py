"""
Automated database migrations for the Cascoin Bridge
This module handles database schema updates automatically.
"""
import logging
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError, OperationalError

logger = logging.getLogger(__name__)

def column_exists(db: Session, table_name: str, column_name: str) -> bool:
    """
    Check if a column exists in a table
    Works with both PostgreSQL and SQLite
    """
    try:
        # Get the database engine type
        engine = db.get_bind()
        inspector = inspect(engine)
        
        # Get columns for the table
        columns = inspector.get_columns(table_name)
        column_names = [col['name'] for col in columns]
        
        return column_name in column_names
    except (ProgrammingError, OperationalError) as e:
        logger.error(f"Database error checking if column {column_name} exists in {table_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking if column {column_name} exists in {table_name}: {e}")
        return False

def add_column_if_not_exists(db: Session, table_name: str, column_name: str, column_definition: str):
    """
    Add a column to a table if it doesn't already exist
    """
    try:
        if not column_exists(db, table_name, column_name):
            logger.info(f"Adding column {column_name} to table {table_name}")
            
            # Detect database type
            engine = db.get_bind()
            dialect_name = engine.dialect.name
            
            if dialect_name == 'postgresql':
                # PostgreSQL syntax
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            elif dialect_name == 'sqlite':
                # SQLite syntax
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            else:
                logger.warning(f"Unknown database dialect: {dialect_name}, using standard SQL")
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            
            db.execute(text(sql))
            db.commit()
            logger.info(f"Successfully added column {column_name} to {table_name}")
        else:
            logger.info(f"Column {column_name} already exists in {table_name}, skipping")
    except (ProgrammingError, OperationalError) as e:
        logger.error(f"Error adding column {column_name} to {table_name}: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding column {column_name} to {table_name}: {e}")
        db.rollback()
        raise

def update_existing_records(db: Session, table_name: str, column_name: str, default_value):
    """
    Update existing records to have default values for new columns
    """
    try:
        if column_exists(db, table_name, column_name):
            # Check if there are any NULL values to update
            check_sql = f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} IS NULL"
            result = db.execute(text(check_sql)).scalar()
            
            if result > 0:
                logger.info(f"Updating {result} NULL values in {table_name}.{column_name} to {default_value}")
                update_sql = f"UPDATE {table_name} SET {column_name} = :default_value WHERE {column_name} IS NULL"
                db.execute(text(update_sql), {"default_value": default_value})
                db.commit()
                logger.info(f"Successfully updated NULL values in {table_name}.{column_name}")
            else:
                logger.info(f"No NULL values found in {table_name}.{column_name}")
    except Exception as e:
        logger.error(f"Error updating existing records in {table_name}.{column_name}: {e}")
        db.rollback()
        raise

def run_confirmation_tracking_migration(db: Session):
    """
    Run the migration to add confirmation tracking columns
    This is the main migration function that should be called during app startup
    """
    logger.info("=== Starting confirmation tracking migration ===")
    
    try:
        # Check if tables exist first
        engine = db.get_bind()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "cas_deposits" not in tables:
            logger.warning("cas_deposits table does not exist yet - skipping migration")
            return
            
        if "polygon_transactions" not in tables:
            logger.warning("polygon_transactions table does not exist yet - skipping migration")
            return
        
        # Migration for cas_deposits table
        logger.info("Checking cas_deposits table...")
        confirmation_columns_added = 0
        
        if not column_exists(db, "cas_deposits", "current_confirmations"):
            add_column_if_not_exists(db, "cas_deposits", "current_confirmations", "INTEGER DEFAULT 0")
            confirmation_columns_added += 1
        else:
            logger.info("✅ current_confirmations already exists in cas_deposits")
            
        if not column_exists(db, "cas_deposits", "required_confirmations"):
            add_column_if_not_exists(db, "cas_deposits", "required_confirmations", "INTEGER DEFAULT 12")
            confirmation_columns_added += 1
        else:
            logger.info("✅ required_confirmations already exists in cas_deposits")
            
        if not column_exists(db, "cas_deposits", "deposit_tx_hash"):
            add_column_if_not_exists(db, "cas_deposits", "deposit_tx_hash", "VARCHAR(255)")
            confirmation_columns_added += 1
        else:
            logger.info("✅ deposit_tx_hash already exists in cas_deposits")
        
        # Update existing records for cas_deposits
        update_existing_records(db, "cas_deposits", "current_confirmations", 0)
        update_existing_records(db, "cas_deposits", "required_confirmations", 12)
        
        # Migration for polygon_transactions table
        logger.info("Checking polygon_transactions table...")
        
        if not column_exists(db, "polygon_transactions", "current_confirmations"):
            add_column_if_not_exists(db, "polygon_transactions", "current_confirmations", "INTEGER DEFAULT 0")
            confirmation_columns_added += 1
        else:
            logger.info("✅ current_confirmations already exists in polygon_transactions")
            
        if not column_exists(db, "polygon_transactions", "required_confirmations"):
            add_column_if_not_exists(db, "polygon_transactions", "required_confirmations", "INTEGER DEFAULT 12")
            confirmation_columns_added += 1
        else:
            logger.info("✅ required_confirmations already exists in polygon_transactions")
        
        # Update existing records for polygon_transactions
        update_existing_records(db, "polygon_transactions", "current_confirmations", 0)
        update_existing_records(db, "polygon_transactions", "required_confirmations", 12)
        
        if confirmation_columns_added > 0:
            logger.info(f"✅ Added {confirmation_columns_added} confirmation tracking columns!")
        else:
            logger.info("✅ All confirmation tracking columns already exist!")
            
        logger.info("🎉 Confirmation tracking migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error("Full error details:", exc_info=True)
        # Don't re-raise the exception to avoid breaking the entire initialization
        # The tables might already be created correctly by SQLAlchemy models

def run_all_migrations(db: Session):
    """
    Run all database migrations
    Add new migrations here as needed
    """
    logger.info("Running all database migrations...")
    
    try:
        # Run confirmation tracking migration
        run_confirmation_tracking_migration(db)
        
        # Run polygon gas deposits migration (BYO-gas flow)
        run_polygon_gas_deposits_migration(db)
        
        # Add future migrations here:
        # run_future_migration_1(db)
        # run_future_migration_2(db)
        
        logger.info("All migrations completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration process failed: {e}")
        raise

def table_exists(db: Session, table_name: str) -> bool:
    """
    Check if a table exists in the database
    """
    try:
        engine = db.get_bind()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return table_name in tables
    except Exception as e:
        logger.error(f"Error checking if table {table_name} exists: {e}")
        return False

def run_polygon_gas_deposits_migration(db: Session):
    """
    Run the migration to create polygon_gas_deposits table for BYO-gas flow
    """
    logger.info("=== Starting polygon_gas_deposits migration ===")
    
    try:
        # Check if table already exists
        if table_exists(db, "polygon_gas_deposits"):
            logger.info("✅ polygon_gas_deposits table already exists, skipping creation")
            return
        
        logger.info("Creating polygon_gas_deposits table...")
        
        # Detect database type for appropriate SQL
        engine = db.get_bind()
        dialect_name = engine.dialect.name
        
        if dialect_name == 'sqlite':
            # SQLite version
            create_table_sql = """
            CREATE TABLE polygon_gas_deposits (
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
            )
            """
            
            # Create indexes
            indexes_sql = [
                "CREATE INDEX idx_polygon_gas_deposits_cas_deposit_id ON polygon_gas_deposits(cas_deposit_id)",
                "CREATE INDEX idx_polygon_gas_deposits_status ON polygon_gas_deposits(status)",
                "CREATE INDEX idx_polygon_gas_deposits_address ON polygon_gas_deposits(polygon_gas_address)",
                "CREATE INDEX idx_polygon_gas_deposits_created_at ON polygon_gas_deposits(created_at)"
            ]
            
            # Create trigger for updated_at
            trigger_sql = """
            CREATE TRIGGER update_polygon_gas_deposits_updated_at
                AFTER UPDATE ON polygon_gas_deposits
                FOR EACH ROW
            BEGIN
                UPDATE polygon_gas_deposits 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE id = NEW.id;
            END
            """
            
        elif dialect_name == 'postgresql':
            # PostgreSQL version
            create_table_sql = """
            CREATE TABLE polygon_gas_deposits (
                id SERIAL PRIMARY KEY,
                cas_deposit_id INTEGER NOT NULL,
                polygon_gas_address VARCHAR(42) UNIQUE NOT NULL,
                required_matic DECIMAL(78,18) NOT NULL,
                received_matic DECIMAL(78,18) DEFAULT 0.0,
                status VARCHAR(50) DEFAULT 'pending' NOT NULL,
                hd_index INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (cas_deposit_id) REFERENCES cas_deposits(id),
                
                CONSTRAINT check_status CHECK (status IN ('pending', 'funded', 'spent', 'expired')),
                CONSTRAINT check_required_matic_positive CHECK (required_matic > 0),
                CONSTRAINT check_received_matic_non_negative CHECK (received_matic >= 0),
                CONSTRAINT check_hd_index_non_negative CHECK (hd_index >= 0)
            )
            """
            
            # Create indexes
            indexes_sql = [
                "CREATE INDEX idx_polygon_gas_deposits_cas_deposit_id ON polygon_gas_deposits(cas_deposit_id)",
                "CREATE INDEX idx_polygon_gas_deposits_status ON polygon_gas_deposits(status)",
                "CREATE INDEX idx_polygon_gas_deposits_address ON polygon_gas_deposits(polygon_gas_address)",
                "CREATE INDEX idx_polygon_gas_deposits_created_at ON polygon_gas_deposits(created_at)"
            ]
            
            # Create trigger for updated_at (PostgreSQL syntax)
            trigger_sql = """
            CREATE OR REPLACE FUNCTION update_polygon_gas_deposits_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            
            CREATE TRIGGER update_polygon_gas_deposits_updated_at
                BEFORE UPDATE ON polygon_gas_deposits
                FOR EACH ROW
                EXECUTE FUNCTION update_polygon_gas_deposits_updated_at();
            """
        else:
            logger.warning(f"Unknown database dialect: {dialect_name}, using SQLite syntax")
            # Fallback to SQLite syntax
            create_table_sql = """
            CREATE TABLE polygon_gas_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cas_deposit_id INTEGER NOT NULL,
                polygon_gas_address VARCHAR(42) UNIQUE NOT NULL,
                required_matic DECIMAL(78,18) NOT NULL,
                received_matic DECIMAL(78,18) DEFAULT 0.0,
                status VARCHAR(50) DEFAULT 'pending' NOT NULL,
                hd_index INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (cas_deposit_id) REFERENCES cas_deposits(id)
            )
            """
            indexes_sql = []
            trigger_sql = ""
        
        # Execute the table creation
        db.execute(text(create_table_sql))
        logger.info("✅ Created polygon_gas_deposits table")
        
        # Create indexes
        for index_sql in indexes_sql:
            try:
                db.execute(text(index_sql))
                logger.info(f"✅ Created index: {index_sql.split('CREATE INDEX ')[1].split(' ON')[0]}")
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")
        
        # Create trigger
        if trigger_sql:
            try:
                db.execute(text(trigger_sql))
                logger.info("✅ Created updated_at trigger")
            except Exception as e:
                logger.warning(f"Failed to create trigger: {e}")
        
        db.commit()
        logger.info("🎉 polygon_gas_deposits migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ polygon_gas_deposits migration failed: {e}")
        logger.error("Full error details:", exc_info=True)
        db.rollback()
        # Don't re-raise to avoid breaking initialization
        # The table might be created by SQLAlchemy models instead

if __name__ == "__main__":
    # This allows the migration to be run standalone for testing
    from backend.database import SessionLocal
    
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        run_all_migrations(db)
    finally:
        db.close() 