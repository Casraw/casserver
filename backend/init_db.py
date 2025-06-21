# backend/init_db.py
import logging
from database.models import create_db_tables
from database.migrations import run_all_migrations
from backend.database import SessionLocal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """
    Initialize database tables and run all migrations
    """
    logger.info("Initializing database tables...")
    create_db_tables()
    logger.info("Database tables initialized.")
    
    # Run automatic migrations
    logger.info("Running database migrations...")
    db = SessionLocal()
    try:
        run_all_migrations(db)
        logger.info("Database migrations completed.")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise
    finally:
        db.close()
    
    logger.info("Database initialization and migration completed successfully!")

if __name__ == "__main__":
    init_database() 