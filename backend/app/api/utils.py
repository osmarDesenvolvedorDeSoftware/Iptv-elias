from __future__ import annotations

from http import HTTPStatus
from typing import Tuple

from flask import Response, jsonify, request
from flask_jwt_extended import get_jwt_identity


def json_error(message: str, status: HTTPStatus) -> Response:
    response = jsonify({"message": message})
    response.status_code = status
    return response


def tenant_from_request() -> Tuple[str | None, Response | None]:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, json_error("Cabeçalho X-Tenant-ID é obrigatório", HTTPStatus.BAD_REQUEST)

    identity = get_jwt_identity() or {}
    if identity.get("tenant_id") != tenant_id:
        return None, json_error("Tenant inválido para o usuário", HTTPStatus.FORBIDDEN)

    return tenant_id, None
