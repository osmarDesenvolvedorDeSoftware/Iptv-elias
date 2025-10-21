from __future__ import annotations

from functools import wraps
from http import HTTPStatus
from typing import Callable, Tuple, TypeVar

from flask import Response, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..models import User

F = TypeVar("F", bound=Callable[..., Response | tuple[Response, int] | tuple[dict, int] | tuple])


def json_error(message: str, status: HTTPStatus) -> Response:
    response = jsonify({"message": message})
    response.status_code = status
    return response


def _parse_identity(identity: object) -> Tuple[int | None, str | None]:
    if isinstance(identity, str):
        user_part, _, tenant_part = identity.partition(":")
        user_id: int | None = None

        if user_part:
            try:
                user_id = int(user_part)
            except ValueError:
                user_id = None

        tenant_id = tenant_part or None
        return user_id, tenant_id

    if isinstance(identity, dict):
        user_value = identity.get("user_id")  # type: ignore[index]
        tenant_value = identity.get("tenant_id")  # type: ignore[index]

        try:
            user_id = int(user_value) if user_value is not None else None
        except (TypeError, ValueError):
            user_id = None

        tenant_id = str(tenant_value) if tenant_value is not None else None
        return user_id, tenant_id

    return None, None


def current_identity() -> Tuple[int | None, str | None]:
    return _parse_identity(get_jwt_identity())


def tenant_from_request() -> Tuple[str | None, Response | None]:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, json_error("Cabeçalho X-Tenant-ID é obrigatório", HTTPStatus.BAD_REQUEST)

    _, identity_tenant_id = current_identity()
    if identity_tenant_id != tenant_id:
        return None, json_error("Tenant inválido para o usuário", HTTPStatus.FORBIDDEN)

    return tenant_id, None


def auth_required(fn: F) -> F:
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id, _ = current_identity()
        if user_id is None:
            return json_error("Sessão inválida", HTTPStatus.UNAUTHORIZED)

        user = User.query.get(user_id)
        if not user or not user.is_active:
            return json_error("Usuário não autorizado", HTTPStatus.FORBIDDEN)

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def admin_required(fn: F) -> F:
    @auth_required
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user: User = g.current_user  # type: ignore[assignment]
        if user.role != "admin":
            return json_error("Acesso restrito a administradores", HTTPStatus.FORBIDDEN)
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
