from logging.config import dictConfig

from flask import Flask

from .config import Config
from .extensions import cors, db, init_celery, jwt


def configure_logging(app: Flask) -> None:
    level = app.config.get("LOG_LEVEL", "INFO")
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "format": "{\"time\":\"%(asctime)s\",\"level\":\"%(levelname)s\",\"name\":\"%(name)s\",\"message\":\"%(message)s\"}",
                }
            },
            "handlers": {
                "wsgi": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {
                "level": level,
                "handlers": ["wsgi"],
            },
        }
    )


def register_blueprints(app: Flask) -> None:
    from .api.auth import bp as auth_bp
    from .api.bouquets import bp as bouquets_bp
    from .api.config import bp as config_bp
    from .api.integrations import bp as integrations_bp
    from .api.health import bp as health_bp
    from .api.imports import bp as imports_bp
    from .api.metrics import bp as metrics_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(config_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(bouquets_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(metrics_bp)


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    config_cls = config_object or Config
    app.config.from_object(config_cls())

    configure_logging(app)

    origins = [origin.strip() for origin in app.config.get("CORS_ORIGINS", "*").split(",") if origin]
    cors.init_app(
        app,
        resources={r"/*": {"origins": origins}},
        supports_credentials=True,
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Tenant-ID",
        ],
        expose_headers=["X-Tenant-ID"],
    )

    db.init_app(app)
    jwt.init_app(app)

    register_blueprints(app)

    with app.app_context():
        init_celery(app)

    return app
