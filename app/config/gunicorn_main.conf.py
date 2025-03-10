import os
import logging
from logging.handlers import TimedRotatingFileHandler
from config.config import BASE_DIR

log_directory = os.path.join(BASE_DIR, "logs")
os.makedirs(log_directory, exist_ok=True)

log_file_path = os.path.join(log_directory, "main_app.log")

bind = "0.0.0.0:8000"
workers = 4  # Number of worker processes
worker_class = "uvicorn.workers.UvicornWorker"
loglevel = "info"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7),
        logging.StreamHandler(),
    ]
)

# Gunicorn logging configuration
logger = logging.getLogger('gunicorn.error')
logger.addHandler(TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7))

access_logger = logging.getLogger('gunicorn.access')
access_logger.addHandler(TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7))
