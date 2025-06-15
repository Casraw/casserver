from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api import bridge_api
from backend.api import internal_api # Added
from backend.api import fee_routes # Added for fee calculations
from backend.database import engine #, Base (Models are in database.models now)
from database.models import Base # Import Base from where it's defined
from database.models import create_db_tables

# Create database tables on startup if they don't exist
# In a production app, you might use Alembic for migrations.
# create_db_tables() # Call the function to create tables

app = FastAPI(title="Cascoin-Polygon Bridge API")

@app.on_event("startup")
async def startup_event():
    # This is a good place to ensure tables are created.
    create_db_tables()
    pass

app.include_router(bridge_api.router, prefix="/api", tags=["Bridge Operations"])
app.include_router(internal_api.router, prefix="/internal", tags=["Internal Bridge Operations"]) # Added
app.include_router(fee_routes.router, tags=["Fee Calculations"]) # Added for fee estimates

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
