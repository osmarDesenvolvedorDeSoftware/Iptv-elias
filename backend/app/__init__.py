from logging.config import dictConfig

import flask
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
    from .api.account import bp as account_bp
    from .api.admin import bp as admin_bp
    from .api.auth import bp as auth_bp
    from .api.bouquets import bp as bouquets_bp
    from .api.config import bp as config_bp
    from .api.integrations import bp as integrations_bp
    from .api.health import bp as health_bp
    from .api.imports import bp as imports_bp
    from .api.metrics import bp as metrics_bp
    from .api.tenants import bp as tenants_bp
    from .api.user_settings import bp as user_settings_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(bouquets_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(user_settings_bp)


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    config_cls = config_object or Config
    app.config.from_object(config_cls())

    configure_logging(app)

    configured_origins = app.config.get("CORS_ORIGINS", ["*"])

    if isinstance(configured_origins, str):
        configured_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]

    origins = [origin for origin in configured_origins if origin]
    allow_all_origins = not origins or origins == ["*"]
    cors_origins = "*" if allow_all_origins else origins

    log_origins = "*" if allow_all_origins else ", ".join(origins)
    app.logger.info("CORS allowed origins: %s", log_origins)

    cors.init_app(
        app,
        resources={r"/*": {"origins": cors_origins}},
        supports_credentials=True,
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Tenant-ID",
        ],
        expose_headers=["X-Tenant-ID"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        automatic_options=True,
    )

    @app.after_request
    def add_cors_headers(response):
        """Ensure all responses include the expected CORS headers."""

        origin = flask.request.headers.get("Origin")
        if origin:
            response.headers.add("Access-Control-Allow-Origin", origin)
            response.headers.add("Vary", "Origin")
            response.headers.add(
                "Access-Control-Allow-Headers",
                "Content-Type,Authorization,X-Tenant-ID",
            )
            response.headers.add(
                "Access-Control-Allow-Methods",
                "GET,POST,PUT,PATCH,DELETE,OPTIONS",
            )
        return response

    db.init_app(app)
    jwt.init_app(app)

    register_blueprints(app)

    with app.app_context():
        init_celery(app)

    return app
