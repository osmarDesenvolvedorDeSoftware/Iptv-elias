import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
        self.JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MIN", "15")))
        self.JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "7")))
        self.SQLALCHEMY_DATABASE_URI = os.getenv(
            "SQLALCHEMY_DATABASE_URI", "sqlite:///" + str(BASE_DIR / "app.db")
        )
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", redis_url)
        self.CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", redis_url)
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.PROPAGATE_EXCEPTIONS = True
        self.JWT_TOKEN_LOCATION = ["headers"]
        self.JWT_HEADER_NAME = "Authorization"
        self.JWT_HEADER_TYPE = "Bearer"
        self.JWT_REFRESH_JSON_KEY = "refreshToken"
        self.JWT_ACCESS_TOKEN_EXPIRES_SECONDS = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRES_SECONDS", int(self.JWT_ACCESS_TOKEN_EXPIRES.total_seconds()))
        )
        self.JWT_REFRESH_TOKEN_EXPIRES_SECONDS = int(
            os.getenv("JWT_REFRESH_TOKEN_EXPIRES_SECONDS", int(self.JWT_REFRESH_TOKEN_EXPIRES.total_seconds()))
        )
        self.CELERY_TASK_DEFAULT_QUEUE = "default"
        self.TMDB_API_KEY = os.getenv("TMDB_API_KEY")
        self.TMDB_LANGUAGE = os.getenv("TMDB_LANGUAGE", "pt-BR")
        self.TMDB_REGION = os.getenv("TMDB_REGION", "BR")

    def __call__(self) -> "Config":
        return self
