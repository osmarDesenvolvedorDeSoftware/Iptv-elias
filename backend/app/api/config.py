from __future__ import annotations

from http import HTTPStatus
from typing import Any, Mapping

from flask import Blueprint, Response, g, jsonify, request

from ..models import User
from ..services import settings as settings_service
from .utils import auth_required, json_error, tenant_from_request

bp = Blueprint("config", __name__)


def _extract_override_id(source: Mapping[str, Any] | None = None) -> int | None:
    raw_value: Any = request.args.get("userId")
    if raw_value is None:
        raw_value = request.headers.get("X-User-ID")
    if raw_value is None and source is not None:
        raw_value = source.get("userId")
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensivo
        raise ValueError("Parâmetro 'userId' inválido") from exc


def _resolve_target_user(
    tenant_id: str, *, allow_override: bool, override_id: int | None
) -> tuple[User | None, Response | None]:
    user: User = g.current_user  # type: ignore[assignment]

    if override_id is not None:
        if not allow_override:
            return None, json_error("Acesso restrito a administradores", HTTPStatus.FORBIDDEN)
        if user.role != "admin":
            return None, json_error("Apenas administradores podem selecionar outros usuários", HTTPStatus.FORBIDDEN)
        target = User.query.filter_by(id=override_id, tenant_id=tenant_id).first()
        if not target:
            return None, json_error("Usuário não encontrado para este tenant", HTTPStatus.NOT_FOUND)
        return target, None

    if user.tenant_id != tenant_id:
        return None, json_error("Tenant inválido para o usuário", HTTPStatus.FORBIDDEN)
    return user, None


def _resolve_scope(
    payload: Mapping[str, Any] | None, *, allow_override: bool
) -> tuple[str | None, User | None, Response | None]:
    tenant_id, tenant_error = tenant_from_request()
    if tenant_error:
        return None, None, tenant_error

    try:
        override_id = _extract_override_id(payload)
    except ValueError as exc:
        return None, None, json_error(str(exc), HTTPStatus.BAD_REQUEST)

    user, user_error = _resolve_target_user(
        tenant_id,
        allow_override=allow_override,
        override_id=override_id,
    )
    if user_error:
        return None, None, user_error

    return tenant_id, user, None


@bp.get("/config")
@auth_required
def get_config():
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None  # for mypy

    config = settings_service.get_settings(tenant_id, user.id)
    return jsonify(config), HTTPStatus.OK


@bp.post("/config")
@auth_required
def update_config():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, user, error = _resolve_scope(payload, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    payload.pop("userId", None)

    try:
        config = settings_service.save_settings(tenant_id, user.id, payload)
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
@auth_required
def get_config_schema():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    schema = settings_service.get_schema()
    return jsonify(schema), HTTPStatus.OK


@bp.post("/config/test")
@auth_required
def test_config():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, user, error = _resolve_scope(payload, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    payload.pop("userId", None)

    try:
        success, message, meta = settings_service.test_connection(tenant_id, user.id, payload)
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
@auth_required
def reset_config():
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    config = settings_service.reset_settings(tenant_id, user.id)
    return jsonify({"ok": True, "settings": config}), HTTPStatus.OK


@bp.get("/config/me")
@auth_required
def get_config_me():
    tenant_id, user, error = _resolve_scope(None, allow_override=False)
    if error:
        return error
    assert tenant_id is not None and user is not None

    config = settings_service.get_settings(tenant_id, user.id)
    return jsonify(config), HTTPStatus.OK


@bp.post("/config/me")
@auth_required
def update_config_me():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, user, error = _resolve_scope(payload, allow_override=False)
    if error:
        return error
    assert tenant_id is not None and user is not None

    payload.pop("userId", None)

    try:
        config = settings_service.save_settings(tenant_id, user.id, payload)
    except ValueError as exc:
        details = exc.args[0] if exc.args else str(exc)
        response = {"message": "Falha ao salvar configurações"}
        if isinstance(details, list):
            response["errors"] = details
        else:
            response["details"] = details
        return jsonify(response), HTTPStatus.BAD_REQUEST

    return jsonify({"ok": True, "settings": config}), HTTPStatus.OK


@bp.post("/config/me/test")
@auth_required
def test_config_me():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, user, error = _resolve_scope(payload, allow_override=False)
    if error:
        return error
    assert tenant_id is not None and user is not None

    payload.pop("userId", None)

    try:
        success, message, meta = settings_service.test_connection(tenant_id, user.id, payload)
    except ValueError as exc:
        details = exc.args[0] if exc.args else str(exc)
        response = {"message": "Configurações inválidas"}
        if isinstance(details, list):
            response["errors"] = details
        else:
            response["details"] = details
        return jsonify(response), HTTPStatus.BAD_REQUEST

    return jsonify({"success": success, "message": message, **meta}), HTTPStatus.OK


@bp.post("/config/me/reset")
@auth_required
def reset_config_me():
    tenant_id, user, error = _resolve_scope(None, allow_override=False)
    if error:
        return error
    assert tenant_id is not None and user is not None

    config = settings_service.reset_settings(tenant_id, user.id)
    return jsonify({"ok": True, "settings": config}), HTTPStatus.OK
