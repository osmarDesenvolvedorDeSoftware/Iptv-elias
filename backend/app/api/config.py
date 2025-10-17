from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from ..services.configs import get_config as load_config, save_config
from .utils import json_error, tenant_from_request

bp = Blueprint("config", __name__)


@bp.get("/config")
@jwt_required()
def get_config():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    config = load_config(tenant_id)
    return jsonify(config), HTTPStatus.OK


@bp.post("/config")
@jwt_required()
def update_config():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    try:
        _, requires_restart = save_config(tenant_id, payload)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    return (
        jsonify(
            {
                "ok": True,
                "requiresWorkerRestart": requires_restart,
            }
        ),
        HTTPStatus.OK,
    )
