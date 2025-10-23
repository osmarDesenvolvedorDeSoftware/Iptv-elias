from __future__ import annotations

import base64
import hashlib
import logging
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Tuple
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from pydantic import BaseModel, Field, ValidationError, validator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import Unauthorized

from ..extensions import db
from ..models import Setting, TenantIntegrationConfig, User
from .mysql_errors import (
    ACCESS_DENIED,
    SSL_MISCONFIG_ERROR_CODE,
    SSL_MISCONFIG_ERROR_MESSAGE,
    build_access_denied_response,
    is_access_denied_error,
    is_ssl_misconfiguration_error,
)

logger = logging.getLogger(__name__)


def _password_state(value: Any) -> str:
    if value is None:
        return "unset"
    if isinstance(value, str) and value == "":
        return "blank"
    return "provided"


def _ensure_url(value: URL | str | None) -> URL | None:
    if value is None:
        return None
    if isinstance(value, URL):
        return value
    try:
        return make_url(value)
    except Exception:
        return None


def _render_safe_url(value: URL | str | None) -> str:
    if value is None:
        return "<nenhuma>"
    url = _ensure_url(value)
    if url is None:
        return str(value)
    try:
        return url.render_as_string(hide_password=True)
    except Exception:
        return str(value)


_GENERAL_KEY = "general"
_SENSITIVE_FIELDS = {"db_pass", "xtream_pass", "tmdb_key"}


def _cipher() -> Fernet:
    secret = current_app.config.get("SECRET_KEY", "dev-secret")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _encrypt(value: str) -> str:
    if not value:
        return ""
    return _cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _cipher().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


class SettingsPayload(BaseModel):
    db_host: str = Field(..., min_length=1, max_length=255)
    db_port: int = Field(..., ge=1, le=65535)
    db_user: str = Field(..., min_length=1, max_length=255)
    db_pass: str | None = Field(default=None)
    db_name: str = Field(..., min_length=1, max_length=255)
    api_base_url: str | None = Field(default="", max_length=512)
    m3u_link: str | None = Field(default="", max_length=1024)
    tmdb_key: str | None = Field(default=None, max_length=128)
    xtream_user: str | None = Field(default="", max_length=255)
    xtream_pass: str | None = Field(default=None, max_length=255)
    use_xtream_api: bool = Field(default=True)
    bouquet_normal: int | None = Field(default=None, ge=0)
    bouquet_adulto: int | None = Field(default=None, ge=0)
    ignored_prefixes: list[str] = Field(default_factory=list)

    class Config:
        anystr_strip_whitespace = True
        extra = "forbid"

    @validator("api_base_url", "m3u_link", pre=True)
    def _normalize_optional_str(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @validator("tmdb_key", "db_pass", "xtream_pass", pre=True)
    def _normalize_secret(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @validator("ignored_prefixes", pre=True, always=True)
    def _normalize_prefixes(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, Iterable):
            raise ValueError("Lista de prefixos inválida")
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Prefixos devem ser textos")
            normalized = item.strip()
            if not normalized or normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            result.append(normalized)
        return result

    @validator("api_base_url")
    def _validate_url(cls, value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("URL base inválida")
        return value

    @validator("m3u_link")
    def _validate_m3u(cls, value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Link M3U inválido")
        return value

    @validator("bouquet_normal", "bouquet_adulto", pre=True)
    def _normalize_bouquet(cls, value: Any) -> int | None:
        if value in (None, "", 0):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError("Identificador de bouquet inválido")
        if parsed < 0:
            raise ValueError("Identificador de bouquet inválido")
        return parsed


_SETTINGS_PAYLOAD_FIELDS = frozenset(SettingsPayload.__fields__.keys())


DEFAULT_SETTINGS: dict[str, Any] = {
    "db_host": "",
    "db_port": 3306,
    "db_user": "",
    "db_pass": None,
    "db_name": "",
    "api_base_url": "",
    "m3u_link": "",
    "tmdb_key": None,
    "xtream_user": "",
    "xtream_pass": None,
    "use_xtream_api": True,
    "bouquet_normal": None,
    "bouquet_adulto": None,
    "ignored_prefixes": [],
    "last_test_status": None,
    "last_test_message": None,
    "last_test_at": None,
}


def _get_setting(tenant_id: str, user_id: int) -> Setting | None:
    return Setting.query.filter_by(tenant_id=tenant_id, user_id=user_id, key=_GENERAL_KEY).first()


def _merge_defaults(value: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_SETTINGS)
    if value:
        merged.update(value)
    return merged


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return str(value)


def _apply_db_columns(setting: Setting | None, value: dict[str, Any]) -> None:
    if setting is None:
        return

    setting.db_host = _normalize_optional_string(value.get("db_host"))

    port_value = value.get("db_port")
    if port_value is None:
        setting.db_port = None
    else:
        try:
            setting.db_port = int(port_value)
        except (TypeError, ValueError):
            setting.db_port = None

    setting.db_user = _normalize_optional_string(value.get("db_user"))
    setting.db_name = _normalize_optional_string(value.get("db_name"))

    password_value = value.get("db_pass")
    if password_value is None:
        setting.db_password = None
    elif isinstance(password_value, str):
        setting.db_password = password_value or None
    else:
        setting.db_password = str(password_value)


def build_mysql_uri(settings: Mapping[str, Any]) -> str | None:
    """Create a SQLAlchemy MySQL URI from a settings mapping."""

    host = _normalize_optional_string(settings.get("db_host"))
    user = _normalize_optional_string(settings.get("db_user"))
    database = _normalize_optional_string(settings.get("db_name"))

    if not host or not user or not database:
        logger.debug(
            "[SETTINGS] build_mysql_uri faltando dados host=%s user=%s database=%s",
            host,
            user,
            database,
        )
        return None

    try:
        port = int(settings.get("db_port") or 3306)
    except (TypeError, ValueError):
        port = 3306

    password = settings.get("db_pass")

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
        "[SETTINGS] build_mysql_uri host=%s port=%s user=%s database=%s password_state=%s driver=%s uri=%s",
        host,
        port,
        user,
        database,
        _password_state(password),
        driver,
        masked_uri,
    )
    if driver != "mysql+pymysql":
        logger.warning(
            "[SETTINGS] build_mysql_uri driver inesperado=%s uri=%s",
            driver,
            masked_uri,
        )

    return url.render_as_string(hide_password=False)


def _mask_mysql_uri(uri: str | None) -> str:
    if not uri:
        return "<nenhuma>"
    try:
        return make_url(uri).render_as_string(hide_password=True)
    except Exception:  # pragma: no cover - prevenção contra URIs inválidas antigas
        return uri


def update_tenant_mysql_uri(tenant_id: str, mysql_uri: str, *, reason: str) -> None:
    sanitized = (mysql_uri or "").strip()
    if not sanitized:
        current_app.logger.debug(
            "[SETTINGS] update_tenant_mysql_uri ignorado - URI vazia (tenant=%s, origem=%s)",
            tenant_id,
            reason,
        )
        return

    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant_id).first()
    if not config:
        current_app.logger.debug(
            "[SETTINGS] update_tenant_mysql_uri ignorado - tenant sem configuração (tenant=%s)",
            tenant_id,
        )
        return

    if config.xui_db_uri == sanitized:
        current_app.logger.debug(
            "[SETTINGS] update_tenant_mysql_uri ignorado - URI inalterada (tenant=%s origem=%s uri=%s)",
            tenant_id,
            reason,
            _mask_mysql_uri(sanitized),
        )
        return

    previous = config.xui_db_uri
    config.xui_db_uri = sanitized
    db.session.commit()

    current_app.logger.info(
        "[SETTINGS] Tenant %s - URI do banco XUI atualizada automaticamente (%s -> %s) [fonte=%s]",
        tenant_id,
        _mask_mysql_uri(previous),
        _mask_mysql_uri(sanitized),
        reason,
    )


def sync_tenant_mysql_uri(tenant_id: str, settings: Mapping[str, Any], *, reason: str) -> None:
    mysql_uri = build_mysql_uri(settings)
    if not mysql_uri:
        logger.debug(
            "[SETTINGS] sync_tenant_mysql_uri ignorado - sem URI calculada (tenant=%s origem=%s)",
            tenant_id,
            reason,
        )
        return
    logger.debug(
        "[SETTINGS] sync_tenant_mysql_uri atualizado (tenant=%s origem=%s uri=%s)",
        tenant_id,
        reason,
        _mask_mysql_uri(mysql_uri),
    )
    update_tenant_mysql_uri(tenant_id, mysql_uri, reason=reason)


def get_or_create_settings(user_id: int) -> Setting:
    """Return the general settings row for a user, creating it if necessary."""

    setting = Setting.query.filter_by(user_id=user_id, key=_GENERAL_KEY).first()
    if setting:
        current_app.logger.info(
            "[SETTINGS] Usuário %s - Configuração existente carregada", user_id
        )
        return setting

    user = User.query.get(user_id)
    if not user:
        raise Unauthorized("Sessão inválida")

    setting = Setting(
        tenant_id=user.tenant_id,
        user_id=user.id,
        key=_GENERAL_KEY,
        value=deepcopy(DEFAULT_SETTINGS),
        updated_at=datetime.utcnow(),
    )
    _apply_db_columns(setting, setting.value)
    db.session.add(setting)
    db.session.commit()

    current_app.logger.info(
        "[SETTINGS] Usuário %s - Configuração criada automaticamente", user.id
    )
    return setting


def get_schema() -> dict[str, Any]:
    return {
        "defaults": deepcopy(DEFAULT_SETTINGS),
        "fields": {
            "db_host": {"type": "string", "label": "Host do MySQL", "required": True},
            "db_port": {"type": "number", "label": "Porta", "required": True, "min": 1, "max": 65535},
            "db_user": {"type": "string", "label": "Usuário", "required": True},
            "db_pass": {"type": "password", "label": "Senha", "required": False},
            "db_name": {"type": "string", "label": "Banco", "required": True},
            "api_base_url": {"type": "url", "label": "URL da API", "required": False},
            "m3u_link": {"type": "url", "label": "Lista M3U", "required": False},
            "tmdb_key": {"type": "password", "label": "Chave TMDb", "required": False},
            "xtream_user": {"type": "string", "label": "Usuário Xtream", "required": False},
            "xtream_pass": {"type": "password", "label": "Senha Xtream", "required": False},
            "use_xtream_api": {"type": "boolean", "label": "Usar API Xtream", "required": True},
            "bouquet_normal": {"type": "number", "label": "Bouquet Normal", "required": False},
            "bouquet_adulto": {"type": "number", "label": "Bouquet Adulto", "required": False},
            "ignored_prefixes": {"type": "list", "label": "Prefixos ignorados", "required": False},
        },
    }


def get_settings(tenant_id: str, user_id: int) -> dict[str, Any]:
    setting = _get_setting(tenant_id, user_id)
    if setting is None:
        setting = get_or_create_settings(user_id)
    merged = _merge_defaults(setting.value if setting else None)

    response = deepcopy(merged)
    for field in _SENSITIVE_FIELDS:
        response[f"{field}_masked"] = bool(merged.get(field))
        response[field] = None

    return response


def get_settings_with_secrets(tenant_id: str, user_id: int) -> dict[str, Any]:
    setting = _get_setting(tenant_id, user_id)
    if setting is None:
        setting = get_or_create_settings(user_id)
    merged = _merge_defaults(setting.value if setting else None)

    for field in _SENSITIVE_FIELDS:
        merged[field] = _decrypt(merged.get(field))

    return merged


def _persist_setting(
    tenant_id: str, user_id: int, value: dict[str, Any], setting: Setting | None = None
) -> None:
    if setting is None:
        setting = _get_setting(tenant_id, user_id)
    if setting is None:
        setting = Setting(
            tenant_id=tenant_id,
            user_id=user_id,
            key=_GENERAL_KEY,
            value=value,
            updated_at=datetime.utcnow(),
        )
        _apply_db_columns(setting, value)
        db.session.add(setting)
    else:
        setting.value = value
        setting.updated_at = datetime.utcnow()
        _apply_db_columns(setting, value)
    db.session.commit()


def save_settings(tenant_id: str, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = SettingsPayload(**payload)
    except ValidationError as exc:
        raise ValueError(exc.errors()) from exc

    setting = _get_setting(tenant_id, user_id)
    current = _merge_defaults(setting.value if setting else None)

    result = current
    update = data.dict()

    for key, value in update.items():
        if key in _SENSITIVE_FIELDS:
            if value is None:
                continue
            if value == "":
                result[key] = None
            else:
                result[key] = _encrypt(value)
        else:
            result[key] = value

    result["last_test_status"] = None
    result["last_test_message"] = None
    result["last_test_at"] = None

    _persist_setting(tenant_id, user_id, result, setting)
    stored_with_secrets = get_settings_with_secrets(tenant_id, user_id)
    sync_tenant_mysql_uri(tenant_id, stored_with_secrets, reason="save_settings")
    return get_settings(tenant_id, user_id)


def reset_settings(tenant_id: str, user_id: int) -> dict[str, Any]:
    setting = _get_setting(tenant_id, user_id)
    if setting:
        db.session.delete(setting)
        db.session.commit()
    return get_settings(tenant_id, user_id)


def update_test_metadata(
    tenant_id: str,
    user_id: int,
    *,
    status: str | None,
    message: str | None,
) -> dict[str, Any]:
    setting = _get_setting(tenant_id, user_id)
    if setting is None:
        setting = get_or_create_settings(user_id)

    merged = _merge_defaults(setting.value if setting else None)
    merged["last_test_status"] = status
    merged["last_test_message"] = message
    merged["last_test_at"] = datetime.utcnow().isoformat() + "Z" if status else None

    _persist_setting(tenant_id, user_id, merged, setting)
    return get_settings(tenant_id, user_id)


def test_connection(tenant_id: str, user_id: int, payload: dict[str, Any]) -> Tuple[bool, str, dict[str, Any]]:
    stored = get_settings_with_secrets(tenant_id, user_id)

    combined: Dict[str, Any] = deepcopy(stored)
    combined.update({k: v for k, v in payload.items() if v is not None})

    filtered_payload = {k: v for k, v in combined.items() if k in _SETTINGS_PAYLOAD_FIELDS}

    try:
        data = SettingsPayload(**filtered_payload)
    except ValidationError as exc:
        raise ValueError(exc.errors()) from exc

    if not data.db_pass:
        raise ValueError("Informe a senha do banco para testar a conexão")

    logger.debug(
        "[SETTINGS] test_connection parâmetros host=%s port=%s user=%s database=%s password_state=%s",
        data.db_host,
        data.db_port,
        data.db_user,
        data.db_name,
        _password_state(data.db_pass),
    )

    url = URL.create(
        "mysql+pymysql",
        username=data.db_user,
        password=data.db_pass,
        host=data.db_host,
        port=data.db_port,
        database=data.db_name,
    )

    masked_uri = _render_safe_url(url)
    driver = url.drivername
    logger.debug(
        "[SETTINGS] test_connection URL=%s driver=%s",
        masked_uri,
        driver,
    )
    if driver != "mysql+pymysql":
        logger.warning(
            "[SETTINGS] test_connection driver inesperado=%s uri=%s",
            driver,
            masked_uri,
        )

    engine: Engine | None = None
    setting = _get_setting(tenant_id, user_id)
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        orig = getattr(exc, "orig", None)
        logger.debug(
            "[SETTINGS] test_connection falhou uri=%s driver=%s exc=%s orig=%r orig_args=%r",
            masked_uri,
            driver,
            exc.__class__.__name__,
            orig,
            getattr(orig, "args", ()),
        )
        stored_value = _merge_defaults(setting.value if setting else None)
        stored_value["last_test_status"] = "error"
        if is_ssl_misconfiguration_error(exc):
            logger.warning(
                "[DB] Detected SSL misconfiguration on remote MySQL host %s (user=%s)",
                data.db_host,
                data.db_user,
            )
            stored_value["last_test_message"] = SSL_MISCONFIG_ERROR_MESSAGE
            stored_value["last_test_at"] = datetime.utcnow().isoformat() + "Z"
            _persist_setting(tenant_id, user_id, stored_value, setting)
            return (
                False,
                SSL_MISCONFIG_ERROR_MESSAGE,
                {
                    "status": "error",
                    "testedAt": stored_value["last_test_at"],
                    "error": {
                        "code": SSL_MISCONFIG_ERROR_CODE,
                        "message": SSL_MISCONFIG_ERROR_MESSAGE,
                    },
                },
            )
        if is_access_denied_error(exc):
            logger.warning(
                "[DB] Access denied while testing remote MySQL host %s (user=%s)",
                data.db_host,
                data.db_user,
            )
            response = build_access_denied_response(user=data.db_user, database=data.db_name)
            message = response["error"]["message"]
            stored_value["last_test_message"] = message
            stored_value["last_test_at"] = datetime.utcnow().isoformat() + "Z"
            _persist_setting(tenant_id, user_id, stored_value, setting)
            return (
                False,
                message,
                {
                    "status": "error",
                    "testedAt": stored_value["last_test_at"],
                    "error": response["error"],
                    "code": ACCESS_DENIED,
                },
            )

        message = str(exc.__cause__ or exc)
        stored_value["last_test_message"] = message
        stored_value["last_test_at"] = datetime.utcnow().isoformat() + "Z"
        _persist_setting(tenant_id, user_id, stored_value, setting)
        return False, message, {"status": "error", "testedAt": stored_value["last_test_at"]}
    finally:
        if engine is not None:
            engine.dispose()

    stored_value = _merge_defaults(setting.value if setting else None)
    stored_value["last_test_status"] = "success"
    stored_value["last_test_message"] = "Conexão estabelecida com sucesso"
    stored_value["last_test_at"] = datetime.utcnow().isoformat() + "Z"
    _persist_setting(tenant_id, user_id, stored_value, setting)

    mysql_uri = build_mysql_uri(data.dict())
    if mysql_uri:
        update_tenant_mysql_uri(tenant_id, mysql_uri, reason="test_connection")

    logger.debug(
        "[SETTINGS] test_connection sucesso uri=%s driver=%s",
        masked_uri,
        driver,
    )

    return True, "Conexão estabelecida com sucesso", {
        "testedAt": stored_value["last_test_at"],
        "status": "success",
    }
