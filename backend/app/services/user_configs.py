from __future__ import annotations

from datetime import datetime
from typing import Any, Tuple

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


def get_user_config(user: User) -> UserConfig:
    """Retorna a configuração do usuário, garantindo que exista."""

    return _ensure_user_config(user)


def update_user_config(user: User, payload: dict[str, Any]) -> Tuple[UserConfig, bool]:
    """Atualiza a configuração IPTV do usuário."""

    config = _ensure_user_config(user)

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

    password = payload.get("password")
    if password is not None:
        password = str(password).strip()
        config.api_password = password or config.api_password

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
    if password is not None and password:
        integration.xtream_password = password
    integration.options = integration.options or {}
    integration.options["active"] = config.active

    db.session.commit()

    return config, bool(base_url)


def mark_sync(user: User) -> None:
    config = user.config
    if not config:
        return
    config.last_sync = datetime.utcnow()
    db.session.commit()
