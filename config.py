import os

PAGE_SIZE = 50

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance/test_platform.db")}'

SCHEDULER_URL="http://localhost:8001"
