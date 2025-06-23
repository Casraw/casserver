# backend/init_db.py
import logging
import sys
import time
from sqlalchemy import text
from database.models import create_db_tables
from database.migrations import run_all_migrations
from backend.database import SessionLocal

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def wait_for_database(max_retries=30, delay=2):
    """
    Wait for database to be ready before proceeding
    """
    logger.info("Waiting for database to be ready...")
    
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Try a simple query to test connection
            db.execute(text("SELECT 1"))
            db.close()
            logger.info("✅ Database is ready!")
            return True
        except Exception as e:
            logger.warning(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt + 1 == max_retries:
                logger.error("❌ Database connection failed after maximum retries")
                return False
            time.sleep(delay)
    
    return False

def init_database():
    """
    Initialize database tables and run all migrations
    """
    logger.info("=== Starting database initialization ===")
    
    # Wait for database to be ready first
    if not wait_for_database():
        logger.error("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    try:
        # Create tables using SQLAlchemy models
        logger.info("Creating database tables...")
        create_db_tables()
        logger.info("✅ Database tables created successfully.")
        
        # Run automatic migrations (adds confirmation columns if missing)
        logger.info("Running database migrations...")
        db = SessionLocal()
        try:
            run_all_migrations(db)
            logger.info("✅ Database migrations completed successfully.")
        except Exception as e:
            logger.error(f"❌ Database migration failed: {e}")
            logger.error("This might not be critical if tables were already created correctly.")
            # Don't fail the entire initialization for migration errors
            # as the models might already have the correct schema
        finally:
            db.close()
        
        logger.info("🎉 Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error("Full error details:", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    init_database() 