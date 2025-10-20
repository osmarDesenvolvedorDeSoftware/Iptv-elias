from __future__ import annotations

from typing import Optional

from celery import Celery
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

from .config import Config


db = SQLAlchemy()
jwt = JWTManager()
cors = CORS(supports_credentials=True)
celery_app = Celery(__name__)

_flask_app: Optional[Flask] = None


def _create_standalone_app() -> Flask:
    """Cria uma instância mínima do Flask para execução do worker."""

    app = Flask("celery_worker")
    app.config.from_object(Config())

    db.init_app(app)
    jwt.init_app(app)

    return app


def init_celery(app: Optional[Flask] = None) -> Celery:
    global _flask_app

    if app is None:
        if _flask_app is None:
            _flask_app = _create_standalone_app()
        flask_app = _flask_app
    else:
        _flask_app = app
        flask_app = app

    celery_app.conf.update(
        broker_url=flask_app.config["CELERY_BROKER_URL"],
        result_backend=flask_app.config["CELERY_RESULT_BACKEND"],
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_default_queue=flask_app.config.get("CELERY_TASK_DEFAULT_QUEUE", "default"),
    )

    celery_app.autodiscover_tasks(["app"], force=True)

    class ContextTask(celery_app.Task):  # type: ignore[misc]
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return super().__call__(*args, **kwargs)

    celery_app.Task = ContextTask

    return celery_app


# Garante que o worker configure o Celery mesmo sem passar pelo create_app
init_celery()
