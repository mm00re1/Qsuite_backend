import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import BASE_DIR
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from sqlalchemy.orm import Session
from models.models import engine, Base, TestGroup, TestCase, TestResult, SessionLocal
from utils import parse_time_to_cron
from endpoints import view_dates, modify_test_cases, add_view_test_results, add_view_test_groups, search_tests, view_tests, run_q_code

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Ensure the db directory exists
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

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

# Initialize the scheduler
scheduler = AsyncIOScheduler()
#scheduler.add_jobstore('default')

def run_scheduled_test_group(test_group_id: int):
    logger.info(f"Running scheduled job for TestGroup ID: {test_group_id}")
    """Runs scheduled tests for a given test group."""
    session: Session = SessionLocal()

    try:
        test_group = session.query(TestGroup).filter(TestGroup.id == test_group_id).first()
        if not test_group:
            logging.error(f"TestGroup ID {test_group_id} not found.")
            return

        # Retrieve test cases for the group
        test_cases = session.query(TestCase).filter(TestCase.group_id == test_group_id).all()
        
        for test_case in test_cases:
            start_time = datetime.utcnow()
            if test_case.free_form:
                code_lines = test_case.test_code.split('\n\n')
                kdbQuery = wrapQcode(request.code)
                result = sendFreeFormQuery(kdbQuery, test_group.server, test_group.port, test_group.tls, [])

            else:   # test is a predefined q function
                result = sendFunctionalQuery(test_name, test_group.server, test_group.port, test_group.tls)

            time_taken = (datetime.utcnow() - start_time).total_seconds()
            if result["success"]:
                err_message = ""
            elif result["message"] == "Response Preview":
                err_message = "Response was not Boolean"
            else:
                err_message = result["message"]


            test_result = TestResult(
                test_case_id = test_case.id,
                group_id = test_group_id,
                date_run = datetime.utcnow().date(),
                time_taken = time_taken,
                pass_status = result["success"],
                error_message = err_message
            )
            session.add(test_result)
            session.commit()
            logging.info(f"Executed test case '{test_case.test_name}' with status: {execution_result['pass_status']}")

    finally:
        session.close()



@app.on_event("startup")
async def startup_event():
    from endpoints.view_dates import initialize_cache
    logging.info("Initialising cache")
    initialize_cache()

    # Start the scheduler
    scheduler.start()

    # Create a new database session
    session: Session = SessionLocal()

    try:
        # Query all test groups
        test_groups = session.query(TestGroup).all()
        for test_group in test_groups:
            if test_group.schedule:
                cron_time = parse_time_to_cron(test_group.schedule)
                if cron_time:
                    # Add a job for each test group based on the parsed schedule
                    scheduler.add_job(
                        run_scheduled_test_group,
                        CronTrigger.from_crontab(f"{cron_time} * * *"),  # Append rest of the cron expression
                        args=[test_group.id],
                        id=str(test_group.id),  # Use the test group ID as the job ID
                        replace_existing=True   # Replace any existing job with the same ID
                    )
                else:
                    logging.warning(f"Skipping TestGroup ID {test_group.id} due to invalid schedule.")
    finally:
        session.close()

@app.on_event("shutdown")
async def shutdown_event():
    # Shutdown the scheduler
    scheduler.shutdown()

# Include the routers
app.include_router(view_dates.router)
app.include_router(modify_test_cases.router)
app.include_router(add_view_test_results.router)
app.include_router(add_view_test_groups.router)
app.include_router(search_tests.router)
app.include_router(view_tests.router)
app.include_router(run_q_code.router)
