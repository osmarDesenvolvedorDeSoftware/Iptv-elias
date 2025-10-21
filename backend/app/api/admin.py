from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from typing import Any
from uuid import uuid4

import bcrypt
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func, or_

from ..extensions import db
from ..models import (
    Job,
    JobLog,
    JobStatus,
    Setting,
    Tenant,
    TenantIntegrationConfig,
    User,
    UserConfig,
)
from ..services import settings as settings_service
from ..services.user_configs import get_user_config, reset_user_panel
from .utils import admin_required, json_error

bp = Blueprint("admin", __name__, url_prefix="/admin")

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _parse_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _normalize_status_filter(raw: Any) -> str:
    if not isinstance(raw, str):
        return "all"
    candidate = raw.strip().lower()
    if candidate in {"active", "ativo"}:
        return "active"
    if candidate in {"inactive", "inativo"}:
        return "inactive"
    return "all"


def _serialize_user(
    user: User,
    *,
    job_counts: dict[int, int],
    config_map: dict[int, UserConfig | None],
) -> dict[str, Any]:
    config = config_map.get(user.id)
    last_sync: str | None = None
    if config and config.last_sync:
        last_sync = config.last_sync.isoformat() + "Z"

    panel_summary = None
    if config:
        panel_summary = {
            "domain": config.domain,
            "port": config.port,
            "username": config.api_username,
            "active": config.active,
        }

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "tenantId": user.tenant_id,
        "tenantName": user.tenant.name if user.tenant else None,
        "createdAt": user.created_at.isoformat() + "Z" if user.created_at else None,
        "lastLogin": user.last_login.isoformat() + "Z" if user.last_login else None,
        "status": "active" if user.is_active else "inactive",
        "isActive": bool(user.is_active),
        "syncCount": job_counts.get(user.id, 0),
        "lastSync": last_sync,
        "panel": panel_summary,
    }


def _generate_tenant_id() -> str:
    prefix = current_app.config.get("DEFAULT_TENANT_PREFIX", "user")
    for _ in range(5):
        candidate = f"{prefix}-{uuid4().hex[:8]}"
        if not Tenant.query.filter_by(id=candidate).first():
            return candidate
    return f"{prefix}-{uuid4().hex}"


@bp.get("/users")
@admin_required
def list_users():
    page = _parse_positive_int(request.args.get("page"), DEFAULT_PAGE)
    page_size = _parse_positive_int(request.args.get("pageSize"), DEFAULT_PAGE_SIZE)
    page_size = min(page_size, MAX_PAGE_SIZE)

    query = User.query

    status_filter = _normalize_status_filter(request.args.get("status"))
    if status_filter == "active":
        query = query.filter(User.is_active.is_(True))
    elif status_filter == "inactive":
        query = query.filter(User.is_active.is_(False))

    search = (request.args.get("search") or "").strip()
    if search:
        pattern = f"%{search.lower()}%"
        query = query.filter(
            or_(func.lower(User.name).like(pattern), func.lower(User.email).like(pattern))
        )

    total = query.count()
    if page > 1 and (page - 1) * page_size >= total:
        page = max(DEFAULT_PAGE, (total + page_size - 1) // page_size or DEFAULT_PAGE)

    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_ids = [user.id for user in users]
    job_counts: dict[int, int]
    if user_ids:
        job_counts = dict(
            db.session.query(Job.user_id, func.count(Job.id))
            .filter(Job.user_id.in_(user_ids))
            .group_by(Job.user_id)
            .all()
        )
        config_map = {
            config.user_id: config
            for config in UserConfig.query.filter(UserConfig.user_id.in_(user_ids)).all()
        }
    else:
        job_counts = {}
        config_map = {}

    payload = [
        _serialize_user(user, job_counts=job_counts, config_map=config_map) for user in users
    ]
    response = {
        "items": payload,
        "page": page,
        "pageSize": page_size,
        "total": total,
    }
    return jsonify(response), HTTPStatus.OK


@bp.post("/users")
@admin_required
def create_user():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password_raw = payload.get("password")

    if not name:
        return json_error("Nome é obrigatório", HTTPStatus.BAD_REQUEST)
    if not email:
        return json_error("Email é obrigatório", HTTPStatus.BAD_REQUEST)
    if not isinstance(password_raw, str) or len(password_raw) < 6:
        return json_error("Senha deve ter pelo menos 6 caracteres", HTTPStatus.BAD_REQUEST)

    if User.query.filter(func.lower(User.email) == email).first():
        return json_error("Já existe um usuário com este email", HTTPStatus.CONFLICT)

    is_admin = bool(payload.get("isAdmin") or payload.get("is_admin"))
    is_active = True
    if "isActive" in payload:
        is_active = bool(payload.get("isActive"))
    elif "status" in payload:
        status_flag = _normalize_status_filter(payload.get("status"))
        if status_flag in {"active", "inactive"}:
            is_active = status_flag == "active"

    tenant_name = str(payload.get("tenantName") or name).strip() or name
    tenant_id = _generate_tenant_id()
    tenant = Tenant(id=tenant_id, name=tenant_name)
    db.session.add(tenant)

    password_hash = bcrypt.hashpw(password_raw.encode(), bcrypt.gensalt()).decode()
    user = User(
        tenant_id=tenant_id,
        name=name,
        email=email,
        password_hash=password_hash,
        role="admin" if is_admin else "user",
        is_active=is_active,
    )
    db.session.add(user)
    db.session.flush()

    config = get_user_config(user)

    db.session.commit()

    admin_user = getattr(g, "current_user", None)
    current_app.logger.info(
        "[admin] usuário %s criou conta %s no tenant %s (admin=%s, ativo=%s)",
        getattr(admin_user, "id", "unknown"),
        user.id,
        tenant_id,
        is_admin,
        is_active,
    )

    job_counts = {user.id: 0}
    config_map = {user.id: config}
    return (
        jsonify({"user": _serialize_user(user, job_counts=job_counts, config_map=config_map)}),
        HTTPStatus.CREATED,
    )


@bp.patch("/users/<int:user_id>")
@admin_required
def update_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("Usuário não encontrado", HTTPStatus.NOT_FOUND)

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    changes: list[str] = []

    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            return json_error("Nome é obrigatório", HTTPStatus.BAD_REQUEST)
        if name != user.name:
            user.name = name
            changes.append("name")

    if "email" in payload:
        email = str(payload.get("email") or "").strip().lower()
        if not email:
            return json_error("Email é obrigatório", HTTPStatus.BAD_REQUEST)
        existing = User.query.filter(func.lower(User.email) == email, User.id != user.id).first()
        if existing:
            return json_error("Já existe um usuário com este email", HTTPStatus.CONFLICT)
        if email != user.email:
            user.email = email
            changes.append("email")

    if "password" in payload and payload.get("password"):
        password = str(payload.get("password"))
        if len(password) < 6:
            return json_error("Senha deve ter pelo menos 6 caracteres", HTTPStatus.BAD_REQUEST)
        user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        changes.append("password")

    if "status" in payload:
        status_value = _normalize_status_filter(payload.get("status"))
        if status_value not in {"active", "inactive"}:
            return json_error("Status inválido", HTTPStatus.BAD_REQUEST)
        new_active = status_value == "active"
        if new_active != user.is_active:
            user.is_active = new_active
            changes.append("status")
    elif "isActive" in payload:
        new_active = bool(payload.get("isActive"))
        if new_active != user.is_active:
            user.is_active = new_active
            changes.append("isActive")

    if "isAdmin" in payload:
        new_role = "admin" if bool(payload.get("isAdmin")) else "user"
        if new_role != user.role:
            user.role = new_role
            changes.append("role")

    job_count = db.session.query(func.count(Job.id)).filter(Job.user_id == user.id).scalar() or 0
    config_map = {user.id: user.config}

    if not changes:
        return (
            jsonify(
                {
                    "user": _serialize_user(
                        user, job_counts={user.id: job_count}, config_map=config_map
                    )
                }
            ),
            HTTPStatus.OK,
        )

    db.session.commit()

    admin_user = getattr(g, "current_user", None)
    current_app.logger.info(
        "[admin] usuário %s atualizou conta %s (alterações=%s)",
        getattr(admin_user, "id", "unknown"),
        user.id,
        ",".join(changes),
    )

    return (
        jsonify(
            {
                "user": _serialize_user(
                    user, job_counts={user.id: job_count}, config_map=config_map
                )
            }
        ),
        HTTPStatus.OK,
    )


@bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("Usuário não encontrado", HTTPStatus.NOT_FOUND)

    admin_user = getattr(g, "current_user", None)
    if admin_user and user.id == getattr(admin_user, "id", None):
        return json_error("Você não pode remover a própria conta.", HTTPStatus.BAD_REQUEST)

    tenant_id = user.tenant_id

    job_ids = [job_id for (job_id,) in db.session.query(Job.id).filter_by(user_id=user.id).all()]
    if job_ids:
        db.session.query(JobLog).filter(JobLog.job_id.in_(job_ids)).delete(synchronize_session=False)

    db.session.query(Job).filter(Job.user_id == user.id).delete(synchronize_session=False)
    db.session.query(Setting).filter(Setting.user_id == user.id).delete(synchronize_session=False)
    db.session.query(UserConfig).filter(UserConfig.user_id == user.id).delete(synchronize_session=False)

    db.session.delete(user)

    default_tenant = current_app.config.get("DEFAULT_TENANT_ID")
    if tenant_id and tenant_id != default_tenant:
        db.session.query(TenantIntegrationConfig).filter_by(tenant_id=tenant_id).delete(
            synchronize_session=False
        )
        tenant = Tenant.query.filter_by(id=tenant_id).first()
        if tenant:
            db.session.delete(tenant)

    db.session.commit()

    current_app.logger.info(
        "[admin] usuário %s removeu a conta %s (tenant=%s)",
        getattr(admin_user, "id", "unknown"),
        user_id,
        tenant_id,
    )

    return "", HTTPStatus.NO_CONTENT


@bp.get("/users/<int:user_id>/config")
@admin_required
def get_user_config_details(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("Usuário não encontrado", HTTPStatus.NOT_FOUND)

    settings_payload = settings_service.get_settings_with_secrets(user.tenant_id, user.id)
    panel_config = user.config.to_dict(include_secret=True) if user.config else None

    response = {
        "userId": user.id,
        "tenant": {
            "id": user.tenant_id,
            "name": user.tenant.name if user.tenant else None,
        },
        "settings": settings_payload,
        "panel": panel_config,
    }
    return jsonify(response), HTTPStatus.OK


@bp.post("/users/<int:user_id>/config/reset")
@admin_required
def reset_user_panel_config(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return json_error("Usuário não encontrado", HTTPStatus.NOT_FOUND)

    config = reset_user_panel(user)

    admin_user = getattr(g, "current_user", None)
    current_app.logger.info(
        "[admin] usuário %s resetou o painel XUI da conta %s", 
        getattr(admin_user, "id", "unknown"),
        user.id,
    )

    response = {
        "userId": user.id,
        "panel": config.to_dict(include_secret=True),
        "settings": settings_service.get_settings(user.tenant_id, user.id),
    }
    return jsonify(response), HTTPStatus.OK


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
