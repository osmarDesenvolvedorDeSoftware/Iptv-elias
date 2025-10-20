from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from ..services.xui_integration import get_integration_config, save_integration_config
from .utils import json_error, tenant_from_request

bp = Blueprint("integrations", __name__)


@bp.get("/integrations/xui")
@jwt_required()
def get_xui_integration():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = get_integration_config(tenant_id)
    return jsonify(payload), HTTPStatus.OK


@bp.post("/integrations/xui")
@jwt_required()
def update_xui_integration():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    try:
        updated, requires_restart = save_integration_config(tenant_id, payload)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    return (
        jsonify({"ok": True, "config": updated, "requiresWorkerRestart": requires_restart}),
        HTTPStatus.OK,
    )
