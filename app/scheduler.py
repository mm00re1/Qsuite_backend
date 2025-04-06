import os
import logging
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from uuid import UUID
from models.models import TestGroup, SessionLocal
from utils import parse_time_to_cron
from config.config import BASE_DIR
from KdbSubs import run_scheduled_test_group
from backup_db import perform_backup, cleanup_old_backups


if os.getenv('DOCKER_ENV') == 'true':
    MAIN_URL = "http://main:8000"
else:
    MAIN_URL = "http://localhost:8000"

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
