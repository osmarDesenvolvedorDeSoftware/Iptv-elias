from __future__ import annotations

from http import HTTPStatus
from typing import Any, Tuple

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from ..models import Tenant, User
from ..services.tenants import create_tenant as service_create_tenant, list_tenants as service_list_tenants
from ..services.xui_integration import get_integration_config
from .utils import current_identity, json_error, tenant_from_request

bp = Blueprint("tenants", __name__)


def _serialize_tenant(tenant: Tenant) -> dict[str, Any]:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "createdAt": tenant.created_at.isoformat() if tenant.created_at else None,
    }


def _require_platform_admin() -> Tuple[User | None, Any]:
    header_tenant, header_error = tenant_from_request()
    if header_error:
        return None, header_error

    user_id, tenant_id = current_identity()
    if not user_id or not tenant_id:
        return None, json_error("Sessão inválida", HTTPStatus.UNAUTHORIZED)

    user = User.query.get(user_id)
    if not user:
        return None, json_error("Usuário não encontrado", HTTPStatus.UNAUTHORIZED)

    if user.role != "admin":
        return None, json_error("Apenas administradores podem gerenciar tenants", HTTPStatus.FORBIDDEN)

    default_tenant = current_app.config.get("DEFAULT_TENANT_ID")
    if default_tenant and tenant_id != default_tenant:
        return None, json_error("A operação é permitida apenas no tenant padrão", HTTPStatus.FORBIDDEN)
    if header_tenant and header_tenant != tenant_id:
        return None, json_error("Cabeçalho de tenant inválido", HTTPStatus.FORBIDDEN)

    return user, None


@bp.get("/tenants")
@jwt_required()
def list_tenants():
    _, error = _require_platform_admin()
    if error:
        return error

    tenants = service_list_tenants()
    return jsonify([_serialize_tenant(tenant) for tenant in tenants]), HTTPStatus.OK


@bp.post("/tenants")
@jwt_required()
def create_tenant():
    _, error = _require_platform_admin()
    if error:
        return error

    payload = request.get_json(silent=True) or {}

    tenant_id = payload.get("id") or payload.get("tenantId")
    name = payload.get("name")
    integration = payload.get("integration") if isinstance(payload.get("integration"), dict) else None

    try:
        tenant = service_create_tenant(tenant_id, name, integration)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    response: dict[str, Any] = {
        "ok": True,
        "tenant": _serialize_tenant(tenant),
    }

    if integration:
        response["integration"] = get_integration_config(tenant.id)

    return jsonify(response), HTTPStatus.CREATED


__all__ = ["bp"]
