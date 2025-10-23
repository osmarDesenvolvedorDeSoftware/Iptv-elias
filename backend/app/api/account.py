from __future__ import annotations

import logging
from http import HTTPStatus
from urllib.parse import urlparse
from typing import Any, Mapping

from flask import Blueprint, g, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from ..models import User
from ..services.m3u_parser import parse_m3u_link
from ..services.user_configs import get_user_config, parse_mysql_uri, update_user_config
from .utils import auth_required, json_error

logger = logging.getLogger(__name__)

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.get("/config")
@auth_required
def get_config():
    user: User = g.current_user  # type: ignore[assignment]
    config = get_user_config(user)
    return jsonify(config.to_dict()), HTTPStatus.OK


def _sanitize_for_logging(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy of the payload without sensitive data."""

    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if lowered in {"password", "api_password", "token", "authorization"}:
            sanitized[key] = "<redacted>"
        elif lowered in {"xuidburi", "link", "link_m3u", "linkm3u"}:
            sanitized[key] = "<hidden>"
        elif isinstance(value, (dict, list)):
            sanitized[key] = "<complex>"
        else:
            sanitized[key] = value

    return sanitized


def _split_host(host: str) -> tuple[str, int]:
    """Split a host string with optional port into its components."""

    parsed = urlparse(f"//{host}")
    domain = (parsed.hostname or host).strip()
    port = parsed.port or 80
    if not domain:
        raise ValueError("M3U link inválido ou incompleto")
    return domain, port


@bp.put("/config")
@auth_required
def put_config():
    user: User = g.current_user  # type: ignore[assignment]
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    logger.debug(
        "[account.config] Received payload for user %s: %s",
        user.id,
        _sanitize_for_logging(payload),
    )

    link_payload = payload.get("link_m3u") or payload.get("linkM3u") or payload.get("link")
    if isinstance(link_payload, str) and link_payload.strip():
        try:
            parsed_from_link = parse_m3u_link(link_payload.strip())
            domain, port = _split_host(parsed_from_link["host"])
        except (KeyError, ValueError):
            logger.warning(
                "[account.config] Invalid M3U link for user %s", user.id
            )
            return json_error("Formato de link M3U inválido", HTTPStatus.BAD_REQUEST)

        payload.update(
            {
                "domain": domain,
                "port": port,
                "username": parsed_from_link["username"],
                "password": parsed_from_link["password"],
            }
        )

        logger.debug(
            "[account.config] Parsed M3U link for user %s: host=%s port=%s username=%s",
            user.id,
            parsed_from_link.get("host"),
            port,
            parsed_from_link.get("username"),
        )

    current_config = get_user_config(user)

    domain = payload.get("domain")
    if domain is None:
        domain = current_config.domain
    if isinstance(domain, str):
        domain = domain.strip() or None

    xtream_username = payload.get("username")
    if xtream_username is None:
        xtream_username = current_config.api_username
    if isinstance(xtream_username, str):
        xtream_username = xtream_username.strip() or None

    xtream_password_input = payload.get("password")
    if xtream_password_input is not None:
        xtream_password = str(xtream_password_input).strip()
    else:
        xtream_password = None
    if not xtream_password:
        xtream_password = current_config.api_password

    raw_db_uri = payload.get("xuiDbUri")
    if raw_db_uri is None:
        raw_db_uri = current_config.xui_db_uri

    if raw_db_uri is None:
        db_uri_candidate = None
    elif isinstance(raw_db_uri, str):
        db_uri_candidate = raw_db_uri.strip()
    else:
        db_uri_candidate = str(raw_db_uri).strip()

    db_credentials = None
    connection_ready = False
    logger.debug(
        "[account.config] User %s provided XUI DB URI: %s",
        user.id,
        bool(db_uri_candidate),
    )

    if db_uri_candidate:
        db_credentials = parse_mysql_uri(db_uri_candidate)
        if not db_credentials:
            logger.warning(
                "[account.config] Invalid XUI DB URI for user %s", user.id
            )
            return json_error("URI do banco XUI inválida.", HTTPStatus.BAD_REQUEST)

    if not domain or not xtream_username or not xtream_password:
        logger.warning(
            "[account.config] Missing credentials for user %s: domain=%s username=%s has_password=%s",
            user.id,
            bool(domain),
            bool(xtream_username),
            bool(xtream_password),
        )
        return json_error("Informe domínio, usuário e senha para validar a conexão.", HTTPStatus.BAD_REQUEST)

    if db_credentials is not None:
        url = URL.create(
            "mysql+pymysql",
            username=db_credentials["username"],
            password=db_credentials["password"],
            host=db_credentials["host"],
            port=db_credentials["port"],
            database=db_credentials["database"],
        )

        engine = None
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as connection:  # pragma: no cover - depends on external resource
                connection.execute(text("SELECT 1"))
            connection_ready = True
            logger.info(
                "[account.config] XUI DB connection ok for user %s. Banco local permanece exclusivo do painel; XUI remoto validado sob demanda.",
                user.id,
            )
        except (OperationalError, ProgrammingError) as exc:  # pragma: no cover - depends on external resource
            logger.warning(
                "[account.config] Failed to connect to XUI DB for user %s: %s",
                user.id,
                exc,
            )
            return json_error(
                f"Não foi possível conectar ao banco XUI: {exc}",
                HTTPStatus.BAD_REQUEST,
            )
        except SQLAlchemyError as exc:  # pragma: no cover - depends on external resource
            logger.warning(
                "[account.config] Unexpected SQL error while testing XUI DB for user %s: %s",
                user.id,
                exc,
            )
            return json_error(
                f"Não foi possível conectar ao banco XUI: {exc}",
                HTTPStatus.BAD_REQUEST,
            )
        finally:
            if engine is not None:
                engine.dispose()

        if not connection_ready:
            logger.warning(
                "[account.config] Connection to XUI DB not ready for user %s",
                user.id,
            )
            return json_error(
                "Não foi possível validar a conexão com o banco XUI.",
                HTTPStatus.BAD_REQUEST,
            )

        payload["xuiDbUri"] = db_credentials["uri"]

        logger.debug(
            "[account.config] XUI DB URI validated for user %s: host=%s port=%s user=%s",
            user.id,
            db_credentials.get("host"),
            db_credentials.get("port"),
            db_credentials.get("username"),
        )

    try:
        logger.debug(
            "[account.config] Updating user %s config with keys: %s",
            user.id,
            sorted(payload.keys()),
        )
        config, has_base = update_user_config(user, payload)
    except ValueError as exc:
        logger.warning(
            "[account.config] Failed to update config for user %s: %s",
            user.id,
            exc,
        )
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    response = config.to_dict()
    response["connectionReady"] = connection_ready
    response["hasBase"] = has_base

    logger.debug(
        "[account.config] Updated config for user %s: connection_ready=%s has_base=%s",
        user.id,
        connection_ready,
        has_base,
    )
    return jsonify(response), HTTPStatus.OK


@bp.post("/parse_m3u")
@auth_required
def parse_m3u():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    link = payload.get("link") or payload.get("link_m3u") or payload.get("linkM3u")
    if not isinstance(link, str) or not link.strip():
        return json_error("link_m3u obrigatório", HTTPStatus.BAD_REQUEST)

    try:
        parsed = parse_m3u_link(link.strip())
        domain, port = _split_host(parsed["host"])
    except (KeyError, ValueError):
        return json_error("Formato M3U inválido", HTTPStatus.BAD_REQUEST)

    response = {
        "host": parsed["host"],
        "domain": domain,
        "port": port,
        "username": parsed["username"],
        "password": parsed["password"],
    }

    return jsonify(response), HTTPStatus.OK


@bp.post("/config/test")
@auth_required
def test_config():
    user: User = g.current_user  # type: ignore[assignment]
    config = get_user_config(user)

    if not config.domain or not config.api_username or not config.api_password:
        return json_error(
            "Configure domínio, usuário e senha antes de testar a conexão.",
            HTTPStatus.BAD_REQUEST,
        )

    response = config.to_dict()
    response.update({"ok": True, "message": "Configuração básica válida."})
    return jsonify(response), HTTPStatus.OK
