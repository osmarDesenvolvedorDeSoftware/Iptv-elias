from http import HTTPStatus

import bcrypt
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from ..models import User

bp = Blueprint("auth", __name__)


def _error(message: str, status: HTTPStatus):
    response = jsonify({"message": message})
    response.status_code = status
    return response


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return _error("Email e senha são obrigatórios", HTTPStatus.BAD_REQUEST)

    user = User.query.filter_by(email=email).first()
    if not user:
        return _error("Credenciais inválidas", HTTPStatus.UNAUTHORIZED)

    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return _error("Credenciais inválidas", HTTPStatus.UNAUTHORIZED)

    identity = {"user_id": user.id, "tenant_id": user.tenant_id}
    access_token = create_access_token(identity=identity)
    refresh_token = create_refresh_token(identity=identity)

    response = {
        "token": access_token,
        "refreshToken": refresh_token,
        "expiresInSec": current_app.config["JWT_ACCESS_TOKEN_EXPIRES_SECONDS"],
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "tenantId": user.tenant_id,
        },
    }
    return jsonify(response), HTTPStatus.OK


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    response = {
        "token": access_token,
        "expiresInSec": current_app.config["JWT_ACCESS_TOKEN_EXPIRES_SECONDS"],
    }
    return jsonify(response), HTTPStatus.OK


@bp.post("/logout")
@jwt_required()
def logout():
    return jsonify({"message": "Logout efetuado"}), HTTPStatus.OK
