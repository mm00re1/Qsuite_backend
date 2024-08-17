import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.config import BASE_DIR
import logging
from logging.handlers import TimedRotatingFileHandler
from models.models import engine, Base
from endpoints import view_dates, modify_test_cases, add_view_test_results, add_view_test_groups, search_tests, view_tests, run_q_code


log_directory = os.path.join(BASE_DIR, "logs")

log_file_path = os.path.join(log_directory, "app.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI()

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
Base.metadata.create_all(bind=engine)

@app.on_event("startup")
async def startup_event():
    from endpoints.view_dates import initialize_cache
    logging.info("Initialising cache")
    initialize_cache()

# Include the routers
app.include_router(view_dates.router)
app.include_router(modify_test_cases.router)
app.include_router(add_view_test_results.router)
app.include_router(add_view_test_groups.router)
app.include_router(search_tests.router)
app.include_router(view_tests.router)
app.include_router(run_q_code.router)
