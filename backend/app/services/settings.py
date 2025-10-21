from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, Tuple
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from pydantic import BaseModel, Field, ValidationError, validator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Setting

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


def _get_setting(tenant_id: str) -> Setting | None:
    return Setting.query.filter_by(tenant_id=tenant_id, key=_GENERAL_KEY).first()


def _merge_defaults(value: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_SETTINGS)
    if value:
        merged.update(value)
    return merged


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


def get_settings(tenant_id: str) -> dict[str, Any]:
    setting = _get_setting(tenant_id)
    merged = _merge_defaults(setting.value if setting else None)

    response = deepcopy(merged)
    for field in _SENSITIVE_FIELDS:
        response[f"{field}_masked"] = bool(merged.get(field))
        response[field] = None

    return response


def get_settings_with_secrets(tenant_id: str) -> dict[str, Any]:
    setting = _get_setting(tenant_id)
    merged = _merge_defaults(setting.value if setting else None)

    for field in _SENSITIVE_FIELDS:
        merged[field] = _decrypt(merged.get(field))

    return merged


def _persist_setting(tenant_id: str, value: dict[str, Any], setting: Setting | None = None) -> None:
    if setting is None:
        setting = _get_setting(tenant_id)
    if setting is None:
        setting = Setting(tenant_id=tenant_id, key=_GENERAL_KEY, value=value, updated_at=datetime.utcnow())
        db.session.add(setting)
    else:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    db.session.commit()


def save_settings(tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = SettingsPayload(**payload)
    except ValidationError as exc:
        raise ValueError(exc.errors()) from exc

    setting = _get_setting(tenant_id)
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

    _persist_setting(tenant_id, result, setting)
    return get_settings(tenant_id)


def reset_settings(tenant_id: str) -> dict[str, Any]:
    setting = _get_setting(tenant_id)
    if setting:
        db.session.delete(setting)
        db.session.commit()
    return get_settings(tenant_id)


def test_connection(tenant_id: str, payload: dict[str, Any]) -> Tuple[bool, str, dict[str, Any]]:
    stored = get_settings_with_secrets(tenant_id)

    combined: Dict[str, Any] = deepcopy(stored)
    combined.update({k: v for k, v in payload.items() if v is not None})

    try:
        data = SettingsPayload(**combined)
    except ValidationError as exc:
        raise ValueError(exc.errors()) from exc

    if not data.db_pass:
        raise ValueError("Informe a senha do banco para testar a conexão")

    url = URL.create(
        "mysql+pymysql",
        username=data.db_user,
        password=data.db_pass,
        host=data.db_host,
        port=data.db_port,
        database=data.db_name,
    )

    engine: Engine | None = None
    setting = _get_setting(tenant_id)
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        message = str(exc.__cause__ or exc)
        stored_value = _merge_defaults(setting.value if setting else None)
        stored_value["last_test_status"] = "error"
        stored_value["last_test_message"] = message
        stored_value["last_test_at"] = datetime.utcnow().isoformat() + "Z"
        _persist_setting(tenant_id, stored_value, setting)
        return False, message, {"status": "error", "testedAt": stored_value["last_test_at"]}
    finally:
        if engine is not None:
            engine.dispose()

    stored_value = _merge_defaults(setting.value if setting else None)
    stored_value["last_test_status"] = "success"
    stored_value["last_test_message"] = "Conexão estabelecida com sucesso"
    stored_value["last_test_at"] = datetime.utcnow().isoformat() + "Z"
    _persist_setting(tenant_id, stored_value, setting)

    return True, "Conexão estabelecida com sucesso", {
        "testedAt": stored_value["last_test_at"],
        "status": "success",
    }
