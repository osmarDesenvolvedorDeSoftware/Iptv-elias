from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, g, jsonify, request

from ..models import User
from ..services.user_configs import get_user_config, update_user_config
from .utils import auth_required, json_error

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.get("/config")
@auth_required
def get_config():
    user: User = g.current_user  # type: ignore[assignment]
    config = get_user_config(user)
    return jsonify(config.to_dict()), HTTPStatus.OK


@bp.put("/config")
@auth_required
def put_config():
    user: User = g.current_user  # type: ignore[assignment]
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    try:
        config, has_base = update_user_config(user, payload)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    response = config.to_dict()
    response["connectionReady"] = has_base
    return jsonify(response), HTTPStatus.OK


@bp.post("/config/test")
@auth_required
def test_config():
    user: User = g.current_user  # type: ignore[assignment]
    config = get_user_config(user)

    if not config.domain or not config.api_username or not config.api_password:
        return json_error(
            "Configure domínio, usuário e senha antes de testar a conexão.",
            HTTPStatus.BAD_REQUEST,
        )

    response = config.to_dict()
    response.update({"ok": True, "message": "Configuração básica válida."})
    return jsonify(response), HTTPStatus.OK
