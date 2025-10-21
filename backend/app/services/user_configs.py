from __future__ import annotations

from datetime import datetime
from typing import Any, Tuple
from urllib.parse import quote_plus, urlparse

import bcrypt
from flask import current_app

from ..extensions import db
from ..models import TenantIntegrationConfig, User, UserConfig


def _ensure_user_config(user: User) -> UserConfig:
    config = user.config
    if config is None:
        config = UserConfig(user_id=user.id)
        db.session.add(config)
        db.session.flush()
    return config


def _ensure_integration(tenant_id: str) -> TenantIntegrationConfig:
    integration = TenantIntegrationConfig.query.filter_by(tenant_id=tenant_id).first()
    if integration is None:
        integration = TenantIntegrationConfig(tenant_id=tenant_id, options={})
        db.session.add(integration)
        db.session.flush()
    return integration


def _extract_db_host(domain: str | None) -> str | None:
    if not domain:
        return None
    candidate = domain.strip()
    if not candidate:
        return None
    normalized = candidate
    if not normalized.startswith(("http://", "https://")):
        normalized = f"http://{normalized}"

    parsed = urlparse(normalized)
    hostname = parsed.hostname
    if hostname:
        return hostname
    if ":" in candidate:
        return candidate.split(":", 1)[0]
    return candidate or None


def resolve_xui_db_uri(config: UserConfig) -> str | None:
    uri = config.xui_db_uri.strip() if isinstance(config.xui_db_uri, str) else None
    if uri:
        return uri

    domain = _extract_db_host(config.domain)
    username = config.api_username.strip() if isinstance(config.api_username, str) else None
    password = config.api_password.strip() if isinstance(config.api_password, str) else None

    if not domain or not username or not password:
        return None

    encoded_username = quote_plus(username)
    encoded_password = quote_plus(password)
    return f"mysql+pymysql://{encoded_username}:{encoded_password}@{domain}:3306/xui"


def get_user_config(user: User) -> UserConfig:
    """Retorna a configuração do usuário, garantindo que exista."""

    config = _ensure_user_config(user)
    resolved_uri = resolve_xui_db_uri(config)
    if resolved_uri and config.xui_db_uri != resolved_uri:
        config.xui_db_uri = resolved_uri
        db.session.commit()
    setattr(config, "resolved_xui_db_uri", resolved_uri)
    return config


def update_user_config(user: User, payload: dict[str, Any]) -> Tuple[UserConfig, bool]:
    """Atualiza a configuração IPTV do usuário."""

    config = _ensure_user_config(user)

    raw_xui_uri = payload.get("xuiDbUri")
    if raw_xui_uri is None:
        raw_xui_uri = payload.get("xui_db_uri")
    if raw_xui_uri is not None:
        if isinstance(raw_xui_uri, str):
            trimmed_uri = raw_xui_uri.strip()
        else:
            trimmed_uri = str(raw_xui_uri).strip()
        config.xui_db_uri = trimmed_uri or None

    domain = payload.get("domain")
    if domain is not None:
        config.domain = domain.strip() or None

    port = payload.get("port")
    if port is not None:
        try:
            port_int = int(port) if str(port).strip() else None
        except (TypeError, ValueError):
            raise ValueError("Porta inválida")
        if port_int is not None and (port_int <= 0 or port_int > 65535):
            raise ValueError("Porta fora do intervalo permitido")
        config.port = port_int

    username = payload.get("username")
    if username is not None:
        config.api_username = username.strip() or None

    password_input = payload.get("password")
    new_password: str | None = None
    if password_input is not None:
        candidate = str(password_input).strip()
        if candidate:
            config.api_password = candidate
            config.password_hash = bcrypt.hashpw(candidate.encode(), bcrypt.gensalt()).decode()
            new_password = candidate

    active = payload.get("active")
    if active is not None:
        config.active = bool(active)

    config.updated_at = datetime.utcnow()

    integration = _ensure_integration(user.tenant_id)
    base_url = config.domain or None
    if base_url:
        base_url = base_url.strip()
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            scheme = current_app.config.get("DEFAULT_IPTV_SCHEME", "http")
            base_url = f"{scheme}://{base_url}"
        if config.port:
            base_url = base_url.rstrip("/")
            if ":" in base_url.split("//", 1)[-1]:
                base_url = base_url.rsplit(":", 1)[0]
            base_url = f"{base_url}:{config.port}"
        integration.xtream_base_url = base_url
    else:
        integration.xtream_base_url = None

    integration.xtream_username = config.api_username
    if new_password is not None:
        integration.xtream_password = new_password
    integration.options = integration.options or {}
    integration.options["active"] = config.active

    resolved_uri = resolve_xui_db_uri(config)
    if resolved_uri:
        config.xui_db_uri = resolved_uri
    setattr(config, "resolved_xui_db_uri", resolved_uri)
    integration.xui_db_uri = resolved_uri

    db.session.commit()

    return config, bool(base_url)


def mark_sync(user: User) -> None:
    config = user.config
    if not config:
        return
    config.last_sync = datetime.utcnow()
    db.session.commit()
