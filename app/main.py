import os
from fastapi import Depends, FastAPI
from filelock import FileLock
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from config.config import BASE_DIR
import logging
from logging.handlers import TimedRotatingFileHandler
from models.models import engine, Base
from endpoints import view_dates, modify_test_cases, add_view_test_results, add_view_test_groups, search_tests, view_tests, run_q_code, connection_details, subscriptions
#import secure
from dependencies import PermissionsValidator, validate_token
from encryption_utils import generate_key

OAUTH_ACTIVE = False # Oauth logic uses auth0

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

lock_file_path = os.path.join(BASE_DIR, "init_db.lock")

#csp = secure.ContentSecurityPolicy().default_src("'self'").frame_ancestors("'none'")
##hsts = secure.StrictTransportSecurity().max_age(31536000).include_subdomains()
#referrer = secure.ReferrerPolicy().no_referrer()
#cache_value = secure.CacheControl().no_cache().no_store().max_age(0).must_revalidate()
#x_frame_options = secure.XFrameOptions().deny()

#secure_headers = secure.Secure(
#    csp=csp,
#    #hsts=hsts,
#    referrer=referrer,
#    cache=cache_value,
#    xfo=x_frame_options,
#)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    # Use a file-based lock to ensure only one worker initializes the database
    lock = FileLock(lock_file_path)
    with lock:
        logging.info("Acquiring lock for database initialization...")
        Base.metadata.create_all(bind=engine)
        logging.info("Database initialized successfully.")

    from endpoints.view_dates import initialize_cache
    logging.info("Initializing cache...")
    initialize_cache()

    secret_key_path = os.path.join(BASE_DIR, "secrets/secret.key")
    if not os.path.exists(secret_key_path):
        generate_key()
        logging.info("Encryption key generated and stored securely.")

    # Yield control back to the app (this starts the app)
    yield

app = FastAPI(lifespan=lifespan)

#@app.middleware("http")
#async def set_secure_headers(request, call_next):
#    response = await call_next(request)
#    response.headers["Content-Security-Policy"] = secure_headers["Content-Security-Policy"]
#    #response.headers["Strict-Transport-Security"] = secure_headers["Strict-Transport-Security"]
#    response.headers["Referrer-Policy"] = secure_headers["Referrer-Policy"]
#    response.headers["Cache-Control"] = secure_headers["Cache-Control"]
#    response.headers["X-Frame-Options"] = secure_headers["X-Frame-Options"]
#    return response

#app.add_middleware(
#    CORSMiddleware,
#    allow_origins=[settings.client_origin_url],
#    allow_methods=["GET"],
#    allow_headers=["Authorization", "Content-Type"],
#    max_age=86400,
#)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers, commented out with oauth protection
if OAUTH_ACTIVE:
    app.include_router(view_dates.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(modify_test_cases.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(add_view_test_results.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(add_view_test_groups.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(search_tests.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(view_tests.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(run_q_code.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(connection_details.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
    app.include_router(subscriptions.router, dependencies=[Depends(PermissionsValidator(["read:test_data"]))])
else:
    app.include_router(view_dates.router)
    app.include_router(modify_test_cases.router)
    app.include_router(add_view_test_results.router)
    app.include_router(add_view_test_groups.router)
    app.include_router(search_tests.router)
    app.include_router(view_tests.router)
    app.include_router(run_q_code.router)
    app.include_router(connection_details.router)
    app.include_router(subscriptions.router)
