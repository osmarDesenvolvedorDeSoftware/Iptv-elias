from __future__ import annotations

from copy import deepcopy
from typing import Any, Tuple

from ..extensions import db
from ..models import TenantIntegrationConfig

_DEFAULT_OPTIONS: dict[str, Any] = {
    "tmdb": {
        "enabled": False,
        "apiKey": None,
        "language": "pt-BR",
        "region": "BR",
    },
    "throttleMs": 0,
    "limitItems": None,
    "maxParallel": 2,
    "categoryMapping": {
        "movies": {},
        "series": {},
    },
    "bouquets": {
        "movies": None,
        "series": None,
        "adult": None,
    },
    "adultCategories": [],
    "adultKeywords": [],
    "retry": {
        "enabled": True,
        "maxAttempts": 3,
        "backoffSeconds": 5,
    },
}


def _merge_options(overrides: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(_DEFAULT_OPTIONS)
    if not overrides:
        return result

    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key].update(value)
        else:
            result[key] = value
    return result


def get_integration_config(tenant_id: str) -> dict[str, Any]:
    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant_id).first()
    if not config:
        return {
            "tenantId": tenant_id,
            "xuiDbUri": None,
            "xtreamBaseUrl": None,
            "xtreamUsername": None,
            "hasXtreamPassword": False,
            "options": deepcopy(_DEFAULT_OPTIONS),
        }

    payload = config.to_dict(include_secret=False)
    payload["options"] = _merge_options(payload.get("options"))
    return payload


def save_integration_config(tenant_id: str, payload: dict[str, Any]) -> Tuple[dict[str, Any], bool]:
    if not isinstance(payload, dict):
        raise ValueError("Payload inválido para integração XUI")

    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant_id).first()
    created = False
    if not config:
        config = TenantIntegrationConfig(tenant_id=tenant_id)
        created = True
        db.session.add(config)

    previous = {
        "xui_db_uri": config.xui_db_uri,
        "xtream_base_url": config.xtream_base_url,
        "xtream_username": config.xtream_username,
        "has_password": bool(config.xtream_password),
    }

    if "xuiDbUri" in payload:
        uri = payload.get("xuiDbUri")
        config.xui_db_uri = uri.strip() if isinstance(uri, str) and uri.strip() else None

    if "xtreamBaseUrl" in payload:
        base = payload.get("xtreamBaseUrl")
        if isinstance(base, str):
            sanitized = base.strip().rstrip("/")
        else:
            sanitized = None
        config.xtream_base_url = sanitized or None

    if "xtreamUsername" in payload:
        username = payload.get("xtreamUsername")
        config.xtream_username = username.strip() if isinstance(username, str) and username.strip() else None

    password_updated = False
    if "xtreamPassword" in payload:
        password = payload.get("xtreamPassword")
        if isinstance(password, str):
            trimmed = password.strip()
            config.xtream_password = trimmed or None
            password_updated = True
        else:
            config.xtream_password = None
            password_updated = True

    options = payload.get("options")
    if options is not None:
        if not isinstance(options, dict):
            raise ValueError("Campo 'options' deve ser um objeto")
        merged = _merge_options(options)
        config.options = merged
    elif created and not config.options:
        config.options = deepcopy(_DEFAULT_OPTIONS)

    db.session.commit()

    result = config.to_dict(include_secret=False)
    result["options"] = _merge_options(result.get("options"))

    requires_restart = created
    if not requires_restart:
        requires_restart = password_updated or (
            previous["xui_db_uri"] != config.xui_db_uri
            or previous["xtream_base_url"] != config.xtream_base_url
            or previous["xtream_username"] != config.xtream_username
            or previous["has_password"] != bool(config.xtream_password)
        )
    return result, requires_restart


def require_integration_config(tenant_id: str) -> TenantIntegrationConfig:
    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant_id).first()
    if not config:
        raise RuntimeError("Integração XUI não configurada para o tenant")
    return config


def get_worker_config(tenant_id: str) -> dict[str, Any]:
    config = require_integration_config(tenant_id)
    options = _merge_options(config.options)
    return {
        "xui_db_uri": config.xui_db_uri,
        "xtream_base_url": config.xtream_base_url,
        "xtream_username": config.xtream_username,
        "xtream_password": config.xtream_password,
        "options": options,
    }
