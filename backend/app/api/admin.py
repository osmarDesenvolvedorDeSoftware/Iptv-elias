from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

import bcrypt
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import Job, JobStatus, Tenant, User, UserConfig
from .utils import admin_required, json_error

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _serialize_user(user: User) -> dict[str, object]:
    config = user.config
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "createdAt": user.created_at.isoformat() + "Z" if user.created_at else None,
        "lastLogin": user.last_login.isoformat() + "Z" if user.last_login else None,
        "isActive": user.is_active,
        "tenantId": user.tenant_id,
        "config": config.to_dict() if config else None,
    }


@bp.get("/users")
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [_serialize_user(user) for user in users]}), HTTPStatus.OK


@bp.patch("/users/<int:user_id>")
@admin_required
def update_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("Usuário não encontrado", HTTPStatus.NOT_FOUND)

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        user.name = name.strip()

    role = payload.get("role")
    if role in {"admin", "user"}:
        user.role = role

    if "isActive" in payload:
        user.is_active = bool(payload.get("isActive"))

    password = payload.get("password")
    if isinstance(password, str) and password:
        user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    db.session.commit()
    return jsonify({"user": _serialize_user(user)}), HTTPStatus.OK


@bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("Usuário não encontrado", HTTPStatus.NOT_FOUND)

    tenant = Tenant.query.filter_by(id=user.tenant_id).first()
    Job.query.filter_by(user_id=user.id).delete()
    UserConfig.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    if tenant and tenant.id != current_app.config.get("DEFAULT_TENANT_ID"):
        db.session.delete(tenant)
    db.session.commit()
    return "", HTTPStatus.NO_CONTENT


@bp.get("/dashboard")
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_jobs = Job.query.count()
    failed_jobs = Job.query.filter_by(status=JobStatus.FAILED).count()
    last_sync = (
        db.session.query(func.max(UserConfig.last_sync))
        .filter(UserConfig.last_sync.isnot(None))
        .scalar()
    )

    stats = {
        "totalUsers": total_users,
        "activeUsers": active_users,
        "totalJobs": total_jobs,
        "failedJobs": failed_jobs,
        "lastSync": last_sync.isoformat() + "Z" if isinstance(last_sync, datetime) else None,
    }

    recent_errors = (
        Job.query.filter(Job.status == JobStatus.FAILED)
        .order_by(Job.finished_at.desc().nullslast())
        .limit(10)
        .all()
    )

    error_payload = [
        {
            "id": job.id,
            "type": job.type,
            "tenantId": job.tenant_id,
            "userId": job.user_id,
            "finishedAt": job.finished_at.isoformat() + "Z" if job.finished_at else None,
            "error": job.error,
        }
        for job in recent_errors
    ]

    return jsonify({"stats": stats, "recentErrors": error_payload}), HTTPStatus.OK
