from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from uuid import uuid4

import bcrypt
from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from ..extensions import db
from ..models import Tenant, User
from ..services.user_configs import get_user_config
from .utils import auth_required

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

    if not user.is_active:
        return _error("Conta desativada. Entre em contato com o suporte.", HTTPStatus.FORBIDDEN)

    user.last_login = datetime.utcnow()
    db.session.commit()

    response = _build_login_payload(user)
    return jsonify(response), HTTPStatus.OK


def _build_login_payload(user: User) -> dict[str, object]:
    identity = f"{user.id}:{user.tenant_id}"
    claims = {"role": user.role, "user_id": user.id, "tenant_id": user.tenant_id}
    access_token = create_access_token(identity=identity, additional_claims=claims)
    refresh_token = create_refresh_token(identity=identity)

    payload: dict[str, object] = {
        "token": access_token,
        "refreshToken": refresh_token,
        "expiresInSec": current_app.config["JWT_ACCESS_TOKEN_EXPIRES_SECONDS"],
        "user": _serialize_user(user),
    }
    return payload


def _serialize_user(user: User) -> dict[str, object]:
    tenant_name = user.tenant.name if user.tenant else None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "tenantId": user.tenant_id,
        "tenantName": tenant_name,
        "lastLogin": user.last_login.isoformat() + "Z" if user.last_login else None,
        "isActive": user.is_active,
    }


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()

    if not isinstance(identity, str) or ":" not in identity:
        current_app.logger.warning("[auth] Refresh token com identidade inválida: %s", identity)
        return _error("Sessão inválida", HTTPStatus.UNAUTHORIZED)

    user_id, tenant_id = identity.split(":", 1)
    current_app.logger.info(
        "[auth] Renovando token de acesso para usuário %s no tenant %s", user_id, tenant_id
    )

    user = User.query.filter_by(id=int(user_id), tenant_id=tenant_id).first()
    if not user:
        return _error("Usuário não encontrado", HTTPStatus.UNAUTHORIZED)

    claims = {"role": user.role, "user_id": user.id, "tenant_id": user.tenant_id}
    access_token = create_access_token(identity=identity, additional_claims=claims)
    response = {
        "token": access_token,
        "expiresInSec": current_app.config["JWT_ACCESS_TOKEN_EXPIRES_SECONDS"],
    }
    return jsonify(response), HTTPStatus.OK


@bp.post("/logout")
@jwt_required()
def logout():
    return jsonify({"message": "Logout efetuado"}), HTTPStatus.OK


@bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not name:
        return _error("Nome é obrigatório", HTTPStatus.BAD_REQUEST)
    if not email:
        return _error("Email é obrigatório", HTTPStatus.BAD_REQUEST)
    if not password or len(password) < 6:
        return _error("Senha deve ter pelo menos 6 caracteres", HTTPStatus.BAD_REQUEST)

    if User.query.filter_by(email=email).first():
        return _error("Já existe um usuário com este email", HTTPStatus.CONFLICT)

    tenant_id = _generate_tenant_id()
    tenant = Tenant(id=tenant_id, name=name)
    db.session.add(tenant)

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(tenant_id=tenant_id, name=name, email=email, password_hash=password_hash, role="user")
    user.last_login = datetime.utcnow()
    db.session.add(user)
    db.session.flush()

    get_user_config(user)

    db.session.commit()

    response = _build_login_payload(user)
    return jsonify(response), HTTPStatus.CREATED


@bp.get("/me")
@auth_required
def me():
    user: User = g.current_user  # type: ignore[assignment]
    return jsonify({"user": _serialize_user(user)}), HTTPStatus.OK


def _generate_tenant_id() -> str:
    prefix = current_app.config.get("DEFAULT_TENANT_PREFIX", "user")
    for _ in range(5):
        candidate = f"{prefix}-{uuid4().hex[:8]}"
        if not Tenant.query.filter_by(id=candidate).first():
            return candidate
    return f"{prefix}-{uuid4().hex}"
