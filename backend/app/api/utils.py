from __future__ import annotations

from http import HTTPStatus
from typing import Tuple

from flask import Response, jsonify, request
from flask_jwt_extended import get_jwt_identity


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
