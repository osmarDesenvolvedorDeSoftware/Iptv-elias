from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any, Mapping

from flask import Blueprint, g, jsonify, request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from ..services import settings as settings_service
from ..services.mysql_errors import (
    MysqlAccessDeniedError,
    MysqlSslMisconfigurationError,
    SSL_MISCONFIG_ERROR_MESSAGE,
    build_access_denied_response,
    build_ssl_misconfiguration_response,
    is_access_denied_error,
    is_ssl_misconfiguration_error,
)
from ..services.user_configs import get_user_config, update_user_config
from .utils import auth_required, json_error, tenant_from_request

bp = Blueprint("user_settings", __name__, url_prefix="/api")


logger = logging.getLogger(__name__)


def _mask_password_partial(password: str | None) -> str:
    if password is None:
        return ""

    password_str = str(password)
    if not password_str:
        return ""

    visible = password_str[:3]
    return f"{visible}***"


def _password_state(value: str | None) -> str:
    if value is None:
        return "unset"
    if value == "":
        return "blank"
    return "provided"


def _render_safe_url(url: URL | str | None) -> str:
    if url is None:
        return "<nenhuma>"
    if isinstance(url, str):
        try:
            url = make_url(url)
        except Exception:
            return url
    try:
        return url.render_as_string(hide_password=True)
    except Exception:
        return str(url)


def _render_url_with_partial_password(url: URL | str | None) -> str:
    if url is None:
        return "<nenhuma>"
    if isinstance(url, str):
        try:
            url = make_url(url)
        except Exception:
            return url

    try:
        password = url.password
    except AttributeError:
        return _render_safe_url(url)

    try:
        if password is None:
            return url.render_as_string()

        masked_password = _mask_password_partial(password)
        return url.set(password=masked_password).render_as_string()
    except Exception:
        return _render_safe_url(url)


def _ssl_error_payload() -> dict[str, Any]:
    payload = build_ssl_misconfiguration_response()
    payload["message"] = payload["error"]["message"]
    payload["code"] = payload["error"]["code"]
    return payload


def _access_denied_payload(*, user: str | None, database: str | None) -> dict[str, Any]:
    payload = build_access_denied_response(user=user, database=database)
    payload["message"] = payload["error"]["message"]
    payload["code"] = payload["error"]["code"]
    return payload


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

    logger.debug(
        "[SETTINGS][API] _collect_db_credentials host=%s port=%s user=%s database=%s password_state=%s provided_in_payload=%s payload_keys=%s",
        host,
        port,
        user,
        name,
        _password_state(password),
        password_provided,
        sorted(str(key) for key in payload.keys()),
    )

    return host, port, user, name, password, password_provided


def _build_mysql_uri(host: str, port: int, user: str, password: str | None, database: str) -> str | None:
    if not host or not user or not database:
        logger.debug(
            "[SETTINGS][API] _build_mysql_uri faltando dados host=%s user=%s database=%s",
            host,
            user,
            database,
        )
        return None

    url = URL.create(
        "mysql+pymysql",
        username=user,
        password=password or "",
        host=host,
        port=port,
        database=database,
    )

    masked_uri = _render_safe_url(url)
    driver = url.drivername
    logger.debug(
        "[SETTINGS][API] _build_mysql_uri resultado uri=%s driver=%s password_state=%s",
        masked_uri,
        driver,
        _password_state(password),
    )
    if driver != "mysql+pymysql":
        logger.warning(
            "[SETTINGS][API] _build_mysql_uri driver inesperado=%s uri=%s",
            driver,
            masked_uri,
        )

    return str(url)


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
    if not host or not user or not database:
        raise ValueError("Informe host, usuário e banco do XUI para validar a conexão.")

    logger.debug(
        "[SETTINGS][API] _test_db_connection parâmetros host=%s port=%s user=%s database=%s password_state=%s",
        host,
        port,
        user,
        database,
        _password_state(password),
    )

    url = URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )

    masked_uri = _render_safe_url(url)
    driver = url.drivername
    logger.debug(
        "[SETTINGS][API] _test_db_connection URL=%s driver=%s",
        masked_uri,
        driver,
    )
    logger.info(
        "[DEBUG_DB_CONN] Tentando conectar: user=%s host=%s port=%s db=%s uri=%s",
        user,
        host,
        port,
        database,
        url.render_as_string(hide_password=True),
    )
    logger.info(
        "[DEBUG_DB_CONN] Credenciais SQLAlchemy: user=%s host=%s port=%s db=%s password=%s uri=%s",
        user,
        host,
        port,
        database,
        _mask_password_partial(password),
        _render_url_with_partial_password(url),
    )
    logger.info(
        "[DEBUG_DB_CONN] Senha final para engine: %s",
        _mask_password_partial(password),
    )
    if driver != "mysql+pymysql":
        logger.warning(
            "[SETTINGS][API] _test_db_connection driver inesperado=%s uri=%s",
            driver,
            masked_uri,
        )

    engine: Engine | None = None
    try:
        logger.info("[DEBUG_DB_CONN] Criando engine SQLAlchemy")
        engine = create_engine(url, pool_pre_ping=True)
        logger.info("[DEBUG_DB_CONN] Engine criada")
        with engine.connect() as connection:  # pragma: no cover - depends on external DB
            logger.info("[DEBUG_DB_CONN] Executando SELECT 1")
            connection.execute(text("SELECT 1"))
        logger.info("[DEBUG_DB_CONN] Conexão bem-sucedida")
        logger.debug(
            "[SETTINGS][API] _test_db_connection sucesso uri=%s driver=%s",
            masked_uri,
            driver,
        )
        logger.info(
            "[DB] XUI DB connection ok for host %s. Banco local do painel permanece separado; XUI remoto validado sob demanda.",
            host,
        )
    except (OperationalError, ProgrammingError) as exc:  # pragma: no cover - depends on external DB
        if isinstance(exc, OperationalError):
            orig_args = getattr(exc.orig, "args", [None, None])
            code = orig_args[0] if isinstance(orig_args, (list, tuple)) and len(orig_args) > 0 else None
            message = (
                orig_args[1]
                if isinstance(orig_args, (list, tuple)) and len(orig_args) > 1
                else None
            )
            logger.warning(
                "[DEBUG_DB_CONN] OperationalError: code=%s message=%s",
                code,
                message,
            )
        orig = getattr(exc, "orig", None)
        logger.debug(
            "[SETTINGS][API] _test_db_connection falhou uri=%s driver=%s exc=%s orig=%r orig_args=%r",
            masked_uri,
            driver,
            exc.__class__.__name__,
            orig,
            getattr(orig, "args", ()),
        )
        if is_ssl_misconfiguration_error(exc):
            logger.warning(
                "[DB] Detected SSL misconfiguration on remote MySQL host %s (user=%s)",
                host,
                user or "",
            )
            raise MysqlSslMisconfigurationError(host=host, user=user or "") from exc
        if is_access_denied_error(exc):
            logger.warning(
                "[DB] Access denied by remote MySQL host %s (user=%s)",
                host,
                user or "",
            )
            raise MysqlAccessDeniedError(host=host, user=user or "", database=database) from exc
        raise RuntimeError(f"Não foi possível conectar ao banco XUI: {exc}") from exc
    except SQLAlchemyError as exc:  # pragma: no cover - depends on external DB
        orig = getattr(exc, "orig", None)
        logger.debug(
            "[SETTINGS][API] _test_db_connection erro genérico uri=%s driver=%s exc=%s orig=%r orig_args=%r",
            masked_uri,
            driver,
            exc.__class__.__name__,
            orig,
            getattr(orig, "args", ()),
        )
        raise RuntimeError(f"Não foi possível conectar ao banco XUI: {exc}") from exc
    finally:
        if engine is not None:
            engine.dispose()


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

    logger.debug(
        "[SETTINGS][API] update_settings payload_keys=%s",
        sorted(str(key) for key in payload.keys()),
    )

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
    except MysqlSslMisconfigurationError:
        return jsonify(_ssl_error_payload()), HTTPStatus.BAD_REQUEST
    except MysqlAccessDeniedError as exc:
        payload = _access_denied_payload(user=exc.user or db_user, database=name)
        return jsonify(payload), HTTPStatus.BAD_REQUEST
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
    logger.debug(
        "[SETTINGS][API] update_settings db_uri=%s",
        _render_safe_url(db_uri),
    )
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

    logger.debug(
        "[SETTINGS][API] test_database payload_keys=%s",
        sorted(str(key) for key in payload.keys()),
    )

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
    except MysqlSslMisconfigurationError:
        settings_service.update_test_metadata(
            tenant_id,
            user.id,
            status="error",
            message=SSL_MISCONFIG_ERROR_MESSAGE,
        )
        return jsonify(_ssl_error_payload()), HTTPStatus.BAD_REQUEST
    except MysqlAccessDeniedError as exc:
        payload = _access_denied_payload(user=exc.user or db_user, database=name)
        settings_service.update_test_metadata(
            tenant_id,
            user.id,
            status="error",
            message=payload["error"]["message"],
        )
        return jsonify(payload), HTTPStatus.BAD_REQUEST
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
