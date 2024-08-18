import os

PAGE_SIZE = 50

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance/test_platform.db")}'
CACHE_PATH = os.path.join(BASE_DIR, "cache/unique_dates.json")

SCHEDULER_URL="http://localhost:8001"
