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
from config.config import BASE_DIR, CACHE_PATH
from KdbSubs import sendFreeFormQuery, sendFunctionalQuery, run_subscription_test
from backup_db import perform_backup, cleanup_old_backups
import json

if os.getenv('DOCKER_ENV') == 'true':
    MAIN_URL = "http://main:8000"
else:
    MAIN_URL = "http://localhost:8000"

def set_cache_refresh_flag():
    with open(CACHE_PATH + "refresh_flag.txt", "w") as f:
        f.write("1")  # Set to "1" to indicate cache should be refreshed

# Set up logging configuration
log_directory = os.path.join(BASE_DIR, "logs")
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
                        args=[UUID(test_group.id.hex())],
                        id=test_group.id.hex(),
                        replace_existing=True
                    )
                    logger.info(f"Scheduled job for TestGroup ID {test_group.id.hex()} at {cron_time} * * *")
                else:
                    logger.warning(f"Skipping TestGroup ID {test_group.id.hex()} due to invalid schedule.")

        # Add the job for creating backups of the db
        scheduler.add_job(
            backup_and_cleanup,
            CronTrigger(hour=00, minute=00),  # Runs at midnight
            id="database_backup",
            replace_existing=True
        )
        logger.info("Scheduled daily database backup job at midnight.")

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


def backup_and_cleanup():
    """Performs database backup and cleans up old backups."""
    perform_backup(logger)
    cleanup_old_backups(logger)

def run_scheduled_test_group(test_group_id: UUID):
    """Runs scheduled tests for a given test group."""
    logger.info(f"Running scheduled job for TestGroup ID: {test_group_id.hex}")
    session: Session = SessionLocal()

    try:
        test_group = session.query(TestGroup).filter(TestGroup.id == test_group_id.bytes).first()
        if not test_group:
            logger.error(f"TestGroup ID {test_group_id.hex} not found.")
            return

        # Retrieve test cases for the group
        test_cases = session.query(TestCase).filter(TestCase.group_id == test_group_id.bytes).all()

        for test_case in test_cases:
            start_time = datetime.utcnow()
            if test_case.test_type == "Free-Form":
                code_lines = test_case.test_code.split('\n\n')
                result = sendFreeFormQuery(code_lines, test_group.server, test_group.port, test_group.tls, test_group.scope)

            elif test_case.test_type == "Functional":  # test is a predefined q function
                result = sendFunctionalQuery(test_case.test_code, test_group.server, test_group.port, test_group.tls, test_group.scope)

            elif test_case.test_type == "Subscription":
                # 'test_code' will be JSON with subscription params
                try:
                    config = json.loads(test_case.test_code)
                except Exception:
                    logger.error(f"Error running test case: {str(e)}")

                sub_name = config.get("subscriptionTest", "defaultSub")
                sub_params = config.get("subParams", [])
                number_msgs = config.get("numberOfMessages", 5)
                sub_timeout = config.get("subTimeout", 10)

                # ints for > comparison in run_subscription_test
                number_msgs =int(number_msgs)
                sub_timeout = int(sub_timeout)

                result = run_subscription_test(
                    sub_name=sub_name,
                    kdb_host=test_group.server,
                    kdb_port=test_group.port,
                    kdb_tls=test_group.tls,
                    kdb_scope=test_group.scope,
                    sub_params=sub_params,
                    number_of_messages=number_msgs,
                    timeout_seconds=sub_timeout
                )

            time_taken = (datetime.utcnow() - start_time).total_seconds()
            if result["success"]:
                err_message = ""
            elif result["message"] == "Response Preview":
                err_message = "Response was not Boolean"
            else:
                err_message = result["message"]

            test_result = TestResult(
                test_case_id=test_case.id,
                group_id=test_group_id.bytes,
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
            set_cache_refresh_flag()
            logger.info("Cache refreshed successfully.")
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
                    args=[test_group_id],
                    id=test_group_id.hex,
                    replace_existing=True
                )
                logger.info(f"Updated job for TestGroup ID {test_group_id.hex} at {cron_time} * * *")
            else:
                logger.warning(f"Invalid schedule for TestGroup ID {test_group_id.hex}. Job not added/updated.")
    except Exception as e:
        logger.error(f"Error updating job for TestGroup ID {test_group_id.hex}: {str(e)}")
    finally:
        session.close()

@app.post("/update_job/{test_group_id}")
async def update_job(test_group_id: UUID):
    logger.info("updating or adding job for test group: " + test_group_id.hex)
    jobs = scheduler.get_jobs()
    logger.info(f"Total jobs scheduled: {len(jobs)}")
    add_or_update_job(test_group_id)
    jobs = scheduler.get_jobs()
    logger.info(f"Total jobs scheduled: {len(jobs)}")
    if not jobs:
        logger.info("No jobs currently scheduled.")
    for job in jobs:
        logger.info(f"Job ID: {job.id}")

@app.delete("/remove_job/{test_group_id}")
async def remove_job(test_group_id: UUID):
    try:
        scheduler.remove_job(test_group_id.hex)
        logger.info(f"Removed job for TestGroup ID {test_group_id.hex}")
        jobs = scheduler.get_jobs()
        logger.info(f"Total jobs scheduled: {len(jobs)}")
        return {"message": f"Job for TestGroup ID {test_group_id.hex} removed successfully"}
    except Exception as e:
        logger.error(f"Error removing job for TestGroup ID {test_group_id.hex}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Job for TestGroup ID {test_group_id.hex} not found")
