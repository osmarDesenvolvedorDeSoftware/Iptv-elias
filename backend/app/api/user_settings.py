from __future__ import annotations

from http import HTTPStatus
from typing import Any, Mapping

import pymysql
from flask import Blueprint, g, jsonify, request
from sqlalchemy.engine import URL

from ..services import settings as settings_service
from ..services.user_configs import get_user_config, update_user_config
from .utils import auth_required, json_error, tenant_from_request

bp = Blueprint("user_settings", __name__, url_prefix="/api")


def _get_str(payload: Mapping[str, Any], *keys: str, fallback: Any = None) -> str:
    for key in keys:
        if key in payload and payload[key] is not None:
            value = payload[key]
            if isinstance(value, str):
                return value.strip()
            return str(value)
    if fallback is None:
        return ""
    if isinstance(fallback, str):
        return fallback.strip()
    return str(fallback)


def _collect_db_credentials(
    payload: Mapping[str, Any],
    current: Mapping[str, Any],
) -> tuple[str, int, str, str, str | None, bool]:
    host = _get_str(payload, "db_host", "dbHost", fallback=current.get("db_host"))
    user = _get_str(payload, "db_user", "dbUser", fallback=current.get("db_user"))
    name = _get_str(payload, "db_name", "dbName", fallback=current.get("db_name"))

    port_raw: Any = None
    for key in ("db_port", "dbPort"):
        if key in payload:
            port_raw = payload[key]
            break
    if port_raw is None:
        port_raw = current.get("db_port")
    try:
        port = int(port_raw) if port_raw is not None else 3306
    except (TypeError, ValueError):
        port = 3306

    password_provided = False
    password_raw: Any
    if "db_password" in payload:
        password_raw = payload["db_password"]
        password_provided = True
    elif "dbPassword" in payload:
        password_raw = payload["dbPassword"]
        password_provided = True
    else:
        password_raw = current.get("db_pass")

    if password_provided:
        password: str | None
        if password_raw is None:
            password = None
        else:
            password = str(password_raw)
    else:
        existing = current.get("db_pass")
        password = str(existing) if isinstance(existing, str) else existing

    return host, port, user, name, password, password_provided


def _build_mysql_uri(host: str, port: int, user: str, password: str | None, database: str) -> str | None:
    if not host or not user or not database:
        return None

    return str(
        URL.create(
            "mysql+pymysql",
            username=user,
            password=password or "",
            host=host,
            port=port,
            database=database,
        )
    )


def _serialize_response(config, settings_payload: Mapping[str, Any]) -> dict[str, Any]:
    response = config.to_dict(include_secret=False)

    link_value = settings_payload.get("m3u_link")
    response["link_m3u"] = link_value or None
    response["link"] = link_value or None
    response["db_host"] = settings_payload.get("db_host") or ""
    response["db_port"] = settings_payload.get("db_port")
    response["db_user"] = settings_payload.get("db_user") or ""
    response["db_name"] = settings_payload.get("db_name") or ""
    response["db_pass_masked"] = bool(settings_payload.get("db_pass_masked"))
    response["db_password_masked"] = bool(settings_payload.get("db_pass_masked"))
    response["db_connection_status"] = settings_payload.get("last_test_status")
    response["db_connection_message"] = settings_payload.get("last_test_message")
    response["db_tested_at"] = settings_payload.get("last_test_at")
    response["dbConnectionReady"] = settings_payload.get("last_test_status") == "success"
    response["connectionReady"] = response.get("connectionReady") or response["dbConnectionReady"]

    return response


def _build_settings_payload(
    host: str,
    port: int,
    user: str,
    name: str,
    password: str | None,
    password_provided: bool,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "db_host": host,
        "db_port": port,
        "db_user": user,
        "db_name": name,
    }

    if password_provided:
        body["db_pass"] = password

    link_value = None
    for key in ("link_m3u", "m3u_link", "link", "linkM3u"):
        if key in payload:
            raw = payload.get(key)
            if raw is None:
                link_value = None
            else:
                link_value = str(raw).strip()
            break
    if link_value is not None:
        body["m3u_link"] = link_value

    return body


def _build_user_payload(
    payload: Mapping[str, Any],
    *,
    db_uri: str | None,
) -> dict[str, Any]:
    user_payload: dict[str, Any] = {}

    for key in ("domain", "port", "username", "password", "active"):
        if key in payload:
            user_payload[key] = payload[key]

    if db_uri:
        user_payload["xuiDbUri"] = db_uri

    return user_payload


def _test_db_connection(host: str, port: int, user: str, password: str | None, database: str) -> None:
    if not host or not database:
        raise ValueError("Informe a URI do banco XUI para validar a conexão.")

    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user or "",
            password=password or "",
            database=database,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
            charset="utf8mb4",
        )
    except pymysql.MySQLError as exc:  # pragma: no cover - depends on external DB
        raise RuntimeError(f"Não foi possível conectar ao banco XUI: {exc}") from exc
    else:
        try:
            connection.ping(reconnect=False)
        finally:
            try:
                connection.close()
            except pymysql.MySQLError:
                pass


@bp.get("/settings")
@auth_required
def get_settings():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    user = g.current_user
    config = get_user_config(user)
    settings_payload = settings_service.get_settings(tenant_id, user.id)

    response = _serialize_response(config, settings_payload)
    return jsonify(response), HTTPStatus.OK


@bp.put("/settings")
@auth_required
def update_settings():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, error = tenant_from_request()
    if error:
        return error

    user = g.current_user
    current_settings = settings_service.get_settings_with_secrets(tenant_id, user.id)

    host, port, db_user, name, password, password_provided = _collect_db_credentials(payload, current_settings)

    try:
        _test_db_connection(host, port, db_user, password, name)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)
    except RuntimeError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    settings_payload = _build_settings_payload(host, port, db_user, name, password, password_provided, payload)

    try:
        settings_service.save_settings(tenant_id, user.id, settings_payload)
    except ValueError as exc:
        details = exc.args[0] if exc.args else str(exc)
        response = {"message": "Falha ao salvar configurações"}
        if isinstance(details, list):
            response["errors"] = details
        else:
            response["details"] = details
        return jsonify(response), HTTPStatus.BAD_REQUEST

    db_uri = _build_mysql_uri(host, port, db_user, password, name)
    try:
        config, _ = update_user_config(user, _build_user_payload(payload, db_uri=db_uri))
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    updated_settings = settings_service.update_test_metadata(
        tenant_id,
        user.id,
        status="success",
        message="Conexão estabelecida com sucesso.",
    )

    response = _serialize_response(config, updated_settings)
    response["connectionReady"] = True
    response["dbConnectionReady"] = True
    return jsonify(response), HTTPStatus.OK


@bp.post("/settings/test-db")
@auth_required
def test_database():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, error = tenant_from_request()
    if error:
        return error

    user = g.current_user
    current_settings = settings_service.get_settings_with_secrets(tenant_id, user.id)
    host, port, db_user, name, password, password_provided = _collect_db_credentials(payload, current_settings)

    try:
        _test_db_connection(host, port, db_user, password, name)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)
    except RuntimeError as exc:
        settings_service.update_test_metadata(
            tenant_id,
            user.id,
            status="error",
            message=str(exc),
        )
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    updated_settings = settings_service.update_test_metadata(
        tenant_id,
        user.id,
        status="success",
        message="Conexão estabelecida com sucesso.",
    )

    return (
        jsonify(
            {
                "success": True,
                "message": "Conexão estabelecida com sucesso.",
                "status": "success",
                "testedAt": updated_settings.get("last_test_at"),
            }
        ),
        HTTPStatus.OK,
    )
