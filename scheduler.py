import requests
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from uuid import UUID
from models.models import engine, Base, TestGroup, TestCase, TestResult, SessionLocal
from utils import parse_time_to_cron
from KdbSubs import wrapQcode, sendFreeFormQuery, sendFunctionalQuery

# Set up logging configuration
log_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_directory, exist_ok=True)

log_file_path = os.path.join(log_directory, "scheduler.log")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create and add file handler
file_handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add stream handler for console output
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Initialize FastAPI app for managing scheduler updates
app = FastAPI()

# Initialize the scheduler
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    """Set up jobs on startup."""
    logger.info("Starting to set up the jobs")
    session: Session = SessionLocal()

    try:
        test_groups = session.query(TestGroup).all()
        for test_group in test_groups:
            if test_group.schedule:
                cron_time = parse_time_to_cron(test_group.schedule)
                if cron_time:
                    scheduler.add_job(
                        run_scheduled_test_group,
                        CronTrigger.from_crontab(f"{cron_time} * * *"),
                        args=[test_group.id.bytes],
                        id=str(test_group.id),
                        replace_existing=True
                    )
                    logger.info(f"Scheduled job for TestGroup ID {test_group.id.hex()} at {cron_time} * * *")
                else:
                    logger.warning(f"Skipping TestGroup ID {test_group.id.hex()} due to invalid schedule.")
    except Exception as e:
        logger.error(f"Error scheduling jobs: {str(e)}")
    finally:
        session.close()

    # Start the scheduler
    logger.info("Starting scheduler")
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Shut down the scheduler on app shutdown."""
    logger.info("Shutting down scheduler")
    scheduler.shutdown()

def run_scheduled_test_group(test_group_id: bytes):
    """Runs scheduled tests for a given test group."""
    logger.info(f"Running scheduled job for TestGroup ID: {UUID(bytes=test_group_id).hex()}")
    session: Session = SessionLocal()

    try:
        test_group = session.query(TestGroup).filter(TestGroup.id == test_group_id).first()
        if not test_group:
            logger.error(f"TestGroup ID {UUID(bytes=test_group_id).hex()} not found.")
            return

        # Retrieve test cases for the group
        test_cases = session.query(TestCase).filter(TestCase.group_id == test_group_id).all()

        for test_case in test_cases:
            start_time = datetime.utcnow()
            if test_case.free_form:
                code_lines = test_case.test_code.split('\n\n')
                result = sendFreeFormQuery(code_lines, test_group.server, test_group.port, test_group.tls)
            else:  # test is a predefined q function
                result = sendFunctionalQuery(test_case.test_code, test_group.server, test_group.port, test_group.tls)

            time_taken = (datetime.utcnow() - start_time).total_seconds()
            if result["success"]:
                err_message = ""
            elif result["message"] == "Response Preview":
                err_message = "Response was not Boolean"
            else:
                err_message = result["message"]

            test_result = TestResult(
                test_case_id=test_case.id,
                group_id=test_group_id,
                date_run=datetime.utcnow().date(),
                time_run=datetime.utcnow().time(),
                time_taken=time_taken,
                pass_status=result["success"],
                error_message=err_message
            )
            session.add(test_result)
            session.commit()
            logger.info(f"Executed test case '{test_case.test_name}' with status: {result['success']}")

        # After committing new test results, trigger cache refresh
        try:
            response = requests.post("http://127.0.0.1:8000/refresh_cache/")
            if response.status_code == 200:
                logger.info("Cache refreshed successfully.")
            else:
                logger.error(f"Failed to refresh cache. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error refreshing cache: {str(e)}")

    finally:
        session.close()

def add_or_update_job(test_group_id: UUID):
    session: Session = SessionLocal()

    try:
        test_group = session.query(TestGroup).filter(TestGroup.id == test_group_id.bytes).first()
        if test_group and test_group.schedule:
            cron_time = parse_time_to_cron(test_group.schedule)
            if cron_time:
                scheduler.add_job(
                    run_scheduled_test_group,
                    CronTrigger.from_crontab(f"{cron_time} * * *"),
                    args=[test_group.id.bytes],
                    id=str(test_group.id.hex()),
                    replace_existing=True
                )
                logger.info(f"Updated job for TestGroup ID {test_group.id.hex()} at {cron_time} * * *")
            else:
                logger.warning(f"Invalid schedule for TestGroup ID {test_group.id.hex()}. Job not added/updated.")
    except Exception as e:
        logger.error(f"Error updating job for TestGroup ID {test_group_id.hex()}: {str(e)}")
    finally:
        session.close()

@app.post("/update_job/{test_group_id}")
async def update_job(test_group_id: UUID):
    logger.info("updating or adding job for test group: " + test_group_id.hex())
    jobs = scheduler.get_jobs()
    logger.info(f"Total jobs scheduled: {len(jobs)}")
    add_or_update_job(test_group_id)
    jobs = scheduler.get_jobs()
    logger.info(f"Total jobs scheduled: {len(jobs)}")
    if not jobs:
        logger.info("No jobs currently scheduled.")
    for job in jobs:
        logger.info(f"Job ID: {job.id}")

