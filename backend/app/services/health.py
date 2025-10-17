"""Utilities to verify the health of core backend services."""

from datetime import datetime, timezone
from typing import Any, Dict

from celery.exceptions import CeleryError
from flask import current_app
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import celery_app, db


def _check_database() -> bool:
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def _check_redis(redis_url: str) -> bool:
    try:
        client = Redis.from_url(redis_url)
        try:
            client.ping()
        finally:
            client.close()
        return True
    except RedisError:
        return False


def _check_celery(timeout: float = 2.0) -> bool:
    try:
        result = celery_app.control.ping(timeout=timeout)
        return bool(result)
    except CeleryError:
        return False
    except Exception:
        return False


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def check_system_health() -> Dict[str, Any]:
    services = {
        "database": "ok",
        "redis": "ok",
        "celery": "ok",
    }
    status = "ok"

    if not _check_database():
        services["database"] = "fail"
        status = "degraded"

    redis_url = current_app.config.get("REDIS_URL") or current_app.config.get("CELERY_BROKER_URL")
    if not redis_url or not _check_redis(redis_url):
        services["redis"] = "fail"
        status = "degraded"

    if not _check_celery():
        services["celery"] = "fail"
        status = "degraded"

    return {
        "status": status,
        "services": services,
        "timestamp": _utc_timestamp(),
    }
