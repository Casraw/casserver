#!/usr/bin/env python3
"""
Standalone script to run database migrations manually
Usage: python run_migrations.py
"""
import sys
import os
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.migrations import run_all_migrations
from backend.database import SessionLocal

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting manual database migration...")
    
    try:
        db = SessionLocal()
        try:
            run_all_migrations(db)
            logger.info("✅ All migrations completed successfully!")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 