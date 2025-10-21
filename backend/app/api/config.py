from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from ..services import settings as settings_service
from .utils import json_error, tenant_from_request

bp = Blueprint("config", __name__)


@bp.get("/config")
@jwt_required()
def get_config():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    config = settings_service.get_settings(tenant_id)
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
        config = settings_service.save_settings(tenant_id, payload)
    except ValueError as exc:
        details = exc.args[0] if exc.args else str(exc)
        response = {"message": "Falha ao salvar configurações"}
        if isinstance(details, list):
            response["errors"] = details
        else:
            response["details"] = details
        return jsonify(response), HTTPStatus.BAD_REQUEST

    return (
        jsonify(
            {
                "ok": True,
                "settings": config,
            }
        ),
        HTTPStatus.OK,
    )


@bp.get("/config/schema")
@jwt_required()
def get_config_schema():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    schema = settings_service.get_schema()
    return jsonify(schema), HTTPStatus.OK


@bp.post("/config/test")
@jwt_required()
def test_config():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    try:
        success, message, meta = settings_service.test_connection(tenant_id, payload)
    except ValueError as exc:
        details = exc.args[0] if exc.args else str(exc)
        response = {"message": "Configurações inválidas"}
        if isinstance(details, list):
            response["errors"] = details
        else:
            response["details"] = details
        return jsonify(response), HTTPStatus.BAD_REQUEST

    return jsonify({"success": success, "message": message, **meta}), HTTPStatus.OK


@bp.post("/config/reset")
@jwt_required()
def reset_config():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    config = settings_service.reset_settings(tenant_id)
    return jsonify({"ok": True, "settings": config}), HTTPStatus.OK
