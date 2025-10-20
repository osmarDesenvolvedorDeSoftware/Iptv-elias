"""Serviços auxiliares para gerenciamento de tenants."""

from __future__ import annotations

import re
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Tenant
from .xui_integration import save_integration_config

_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{1,62}[a-z0-9])?$")


def _normalize_tenant_id(raw: str) -> str:
    cleaned = (raw or "").strip().lower()
    if not cleaned:
        raise ValueError("Tenant ID é obrigatório")
    if not _TENANT_ID_PATTERN.match(cleaned):
        raise ValueError(
            "Tenant ID inválido. Utilize apenas letras minúsculas, números, hífens ou underlines (3-64 caracteres)."
        )
    return cleaned


def _normalize_name(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("Nome do tenant é obrigatório")
    return cleaned


def _prepare_integration_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed == "":
                continue
            sanitized[key] = trimmed
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
            sanitized[key] = [str(item).strip() for item in value if str(item).strip()]
        else:
            sanitized[key] = value
    return sanitized


def list_tenants() -> list[Tenant]:
    """Retorna os tenants ordenados pela data de criação."""

    return Tenant.query.order_by(Tenant.created_at.asc()).all()


def create_tenant(tenant_id: str, name: str, integration: dict[str, Any] | None = None) -> Tenant:
    """Cria um novo tenant e opcionalmente aplica uma configuração de integração."""

    normalized_id = _normalize_tenant_id(tenant_id)
    normalized_name = _normalize_name(name)

    if Tenant.query.filter_by(id=normalized_id).first() is not None:
        raise ValueError("Já existe um tenant com esse ID")

    tenant = Tenant(id=normalized_id, name=normalized_name)
    db.session.add(tenant)

    try:
        db.session.commit()
    except IntegrityError as exc:  # pragma: no cover - depende do banco
        db.session.rollback()
        raise ValueError("Não foi possível criar o tenant. Tente novamente.") from exc

    sanitized_integration = _prepare_integration_payload(integration)
    if sanitized_integration:
        try:
            save_integration_config(tenant.id, sanitized_integration)
        except Exception:
            db.session.delete(tenant)
            db.session.commit()
            raise

    return tenant


__all__ = ["list_tenants", "create_tenant"]
