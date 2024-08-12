import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from models.models import TestGroup, TestCase, TestResult, SessionLocal
from utils import parse_time_to_cron
from KdbSubs import wrapQcode, sendFreeFormQuery, sendFunctionalQuery

# Set up logging configuration
log_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_directory, exist_ok=True)

log_file_path = os.path.join(log_directory, "scheduler.log")

# Configure logging
logging.basicConfig(level=logging.INFO)  # Set base level to DEBUG for troubleshooting
logger = logging.getLogger(__name__)

# Create and add file handler
file_handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7)
file_handler.setLevel(logging.INFO)  # Ensure file handler level matches
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add stream handler for console output
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)  # Adjust level if needed
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Initialize the scheduler
scheduler = BlockingScheduler()

def run_scheduled_test_group(test_group_id: int):
    logger.info(f"Running scheduled job for TestGroup ID: {test_group_id}")
    """Runs scheduled tests for a given test group."""
    session: Session = SessionLocal()

    try:
        test_group = session.query(TestGroup).filter(TestGroup.id == test_group_id).first()
        if not test_group:
            logger.error(f"TestGroup ID {test_group_id} not found.")
            return

        # Retrieve test cases for the group
        test_cases = session.query(TestCase).filter(TestCase.group_id == test_group_id).all()

        for test_case in test_cases:
            start_time = datetime.utcnow()
            if test_case.free_form:
                code_lines = test_case.test_code.split('\n\n')
                kdbQuery = wrapQcode(code_lines)
                result = sendFreeFormQuery(kdbQuery, test_group.server, test_group.port, test_group.tls, [])
            else:   # test is a predefined q function
                result = sendFunctionalQuery(test_case.test_code, test_group.server, test_group.port, test_group.tls)

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
            logger.info(f"Executed test case '{test_case.test_name}' with status: {result['success']}")

    finally:
        session.close()

def setup_jobs():
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
                        args=[test_group.id],
                        id=str(test_group.id),
                        replace_existing=True
                    )
                    logger.info(f"Scheduled job for TestGroup ID {test_group.id} at {cron_time} * * *")
                else:
                    logger.warning(f"Skipping TestGroup ID {test_group.id} due to invalid schedule.")
    except Exception as e:
        logger.error(f"Error scheduling jobs: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    setup_jobs()
    logger.info("Starting scheduler")
    scheduler.start()
