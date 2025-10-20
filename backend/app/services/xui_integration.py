from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Tuple

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
    "ignore": {
        "movies": {"categories": [], "prefixes": []},
        "series": {"categories": [], "prefixes": []},
    },
    "retry": {
        "enabled": True,
        "maxAttempts": 3,
        "backoffSeconds": 5,
    },
}


def _clean_string(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def _normalize_string_iterable(values: Any) -> list[str] | None:
    if values is None:
        return None

    normalized: list[str] = []
    iterable: Iterable[Any]

    if isinstance(values, (list, tuple, set)):
        iterable = values
    elif isinstance(values, str):
        iterable = [segment.strip() for segment in values.split(",")]
    else:
        return None

    for entry in iterable:
        if entry is None:
            continue
        text = str(entry).strip()
        if not text:
            continue
        normalized.append(text)
    return normalized


def _collect_ignore_lists(options: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    prefixes: set[str] = set()
    categories: set[str] = set()

    ignore_section = options.get("ignore") if isinstance(options, Mapping) else {}
    if not isinstance(ignore_section, Mapping):
        return [], []

    for scope in ("movies", "series"):
        scope_entry = ignore_section.get(scope)
        if not isinstance(scope_entry, Mapping):
            continue

        raw_categories = scope_entry.get("categories")
        if isinstance(raw_categories, (list, tuple, set)):
            for category in raw_categories:
                if category is None:
                    continue
                text = str(category).strip()
                if text:
                    categories.add(text)

        raw_prefixes = scope_entry.get("prefixes")
        if isinstance(raw_prefixes, (list, tuple, set)):
            for prefix in raw_prefixes:
                if not isinstance(prefix, str):
                    continue
                trimmed = prefix.strip()
                if trimmed:
                    prefixes.add(trimmed)

    return sorted(prefixes), sorted(categories)


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
            "xuiApiUser": None,
            "tmdbKey": None,
            "ignorePrefixes": [],
            "ignoreCategories": [],
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
    merged_options: dict[str, Any] | None = None
    if options is not None:
        if not isinstance(options, dict):
            raise ValueError("Campo 'options' deve ser um objeto")
        merged_options = _merge_options(options)
        config.options = merged_options
    elif created and not config.options:
        merged_options = deepcopy(_DEFAULT_OPTIONS)
        config.options = merged_options
    else:
        merged_options = _merge_options(config.options or {})

    explicit_tmdb_key = _clean_string(payload.get("tmdbKey"))
    tmdb_key = explicit_tmdb_key
    tmdb_options = merged_options.get("tmdb") if isinstance(merged_options, Mapping) else {}
    if tmdb_key is None and isinstance(tmdb_options, Mapping):
        tmdb_key = _clean_string(tmdb_options.get("apiKey"))
    config.tmdb_key = tmdb_key

    explicit_prefixes = _normalize_string_iterable(payload.get("ignorePrefixes"))
    explicit_categories = _normalize_string_iterable(payload.get("ignoreCategories"))
    derived_prefixes, derived_categories = _collect_ignore_lists(merged_options)
    config.ignore_prefixes = explicit_prefixes if explicit_prefixes is not None else derived_prefixes
    config.ignore_categories = explicit_categories if explicit_categories is not None else derived_categories

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
        "xui_api_user": config.xtream_username,
        "xui_api_pass": config.xtream_password,
        "tmdb_key": config.tmdb_key,
        "ignore_prefixes": list(config.ignore_prefixes or []),
        "ignore_categories": list(config.ignore_categories or []),
        "options": options,
    }
