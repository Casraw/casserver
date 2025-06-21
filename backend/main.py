from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api import bridge_api
from backend.api import internal_api # Added
from backend.api import fee_routes # Added for fee calculations
from backend.api import websocket_api # Added for real-time updates
from backend.database import engine, SessionLocal #, Base (Models are in database.models now)
from database.models import Base # Import Base from where it's defined
from database.models import create_db_tables
from database.migrations import run_all_migrations
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Cascoin-Polygon Bridge API")

@app.on_event("startup")
async def startup_event():
    """
    Initialize database and run migrations on startup
    """
    logger.info("Starting Cascoin Bridge API - Initializing database...")
    
    try:
        # Create tables if they don't exist
        create_db_tables()
        logger.info("Database tables created/verified.")
        
        # Run automatic migrations
        logger.info("Running database migrations...")
        db = SessionLocal()
        try:
            run_all_migrations(db)
            logger.info("Database migrations completed successfully.")
        finally:
            db.close()
            
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

app.include_router(bridge_api.router, prefix="/api", tags=["Bridge Operations"])
app.include_router(internal_api.router, prefix="/internal", tags=["Internal Bridge Operations"]) # Added
app.include_router(fee_routes.router, tags=["Fee Calculations"]) # Added for fee estimates
app.include_router(websocket_api.router, prefix="/api", tags=["Real-time Updates"]) # Added for WebSocket

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("frontend/cas_to_poly.html")

@app.get("/poly_to_cas")
async def read_poly_to_cas():
    return FileResponse("frontend/poly_to_cas.html")

@app.get("/fees")
async def read_fee_calculator():
    return FileResponse("frontend/fee_calculator.html")

@app.get("/fee-options")
async def read_fee_comparison():
    return FileResponse("frontend/fee_comparison.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Bridge API is running"}
