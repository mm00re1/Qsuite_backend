import os
from pydantic_settings import BaseSettings
from pydantic import validator

PAGE_SIZE = 50

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance/test_platform.db")}'
CACHE_PATH = os.path.join(BASE_DIR, "cache/")

if os.getenv('DOCKER_ENV') == 'true':
    SCHEDULER_URL = "http://scheduler:8001"
else:
    SCHEDULER_URL = "http://localhost:8001"


class Settings(BaseSettings):
    auth0_audience: str
    auth0_domain: str
    client_origin_url: str
    port: int
    reload: bool

    @classmethod
    @validator("client_origin_url", "auth0_audience", "auth0_domain")
    def check_not_empty(cls, v):
        assert v != "", f"{v} is not defined"
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

