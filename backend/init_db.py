# backend/init_db.py
from database.models import create_db_tables

if __name__ == "__main__":
    print("Initializing database tables...")
    create_db_tables()
    print("Database tables initialized.") 