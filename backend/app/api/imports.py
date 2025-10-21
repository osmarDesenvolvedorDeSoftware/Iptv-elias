from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Mapping

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy.orm import joinedload

from ..models import Job, JobLog, JobStatus, User
from ..services import settings as settings_service
from ..services.jobs import enqueue_import
from .utils import auth_required, json_error, tenant_from_request

bp = Blueprint("imports", __name__)

VALID_IMPORT_TYPES = {"filmes", "series"}


def _extract_user_override(source: Mapping[str, Any] | None = None) -> int | None:
    raw_value = request.args.get("userId")
    if raw_value is None and source is not None:
        raw_value = source.get("userId")
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensivo
        raise ValueError("Parâmetro 'userId' inválido") from exc


def _resolve_scope(
    payload: Mapping[str, Any] | None = None,
    *,
    allow_override: bool,
) -> tuple[str | None, User | None, Response | None]:
    tenant_id, tenant_error = tenant_from_request()
    if tenant_error:
        return None, None, tenant_error

    try:
        override_id = _extract_user_override(payload)
    except ValueError as exc:
        return None, None, json_error(str(exc), HTTPStatus.BAD_REQUEST)

    user: User = g.current_user  # type: ignore[assignment]
    if override_id is not None:
        if not allow_override or user.role != "admin":
            return None, None, json_error("Acesso restrito a administradores", HTTPStatus.FORBIDDEN)
        target = User.query.filter_by(id=override_id, tenant_id=tenant_id).first()
        if not target:
            return None, None, json_error("Usuário não encontrado para este tenant", HTTPStatus.NOT_FOUND)
        settings_service.get_or_create_settings(target.id)
        return tenant_id, target, None

    if user.tenant_id != tenant_id:
        return None, None, json_error("Tenant inválido para o usuário", HTTPStatus.FORBIDDEN)

    settings_service.get_or_create_settings(user.id)

    return tenant_id, user, None


def _parse_log_content(log: JobLog) -> dict[str, Any]:
    try:
        content = json.loads(log.content)
    except json.JSONDecodeError:
        content = {"message": log.content}
    content.setdefault("id", log.id)
    content.setdefault("createdAt", log.created_at.isoformat() + "Z")
    return content


def _job_recent_logs(job: Job, limit: int = 5) -> list[dict[str, Any]]:
    logs = job.logs[-limit:]
    return [_parse_log_content(log) for log in reversed(logs)]


def _job_normalization(job: Job) -> dict[str, Any] | None:
    normalization_log: dict[str, Any] | None = None
    normalization_error: dict[str, Any] | None = None
    for log in job.logs:
        try:
            payload = json.loads(log.content)
        except json.JSONDecodeError:
            continue

        if payload.get("kind") == "normalization":
            normalization_log = {
                "status": "success",
                "logId": log.id,
                "createdAt": log.created_at.isoformat() + "Z",
                "streams": payload.get("streams", {}),
                "series": payload.get("series", {}),
            }
        elif payload.get("kind") == "normalizationError":
            normalization_error = {
                "status": "failed",
                "logId": log.id,
                "createdAt": log.created_at.isoformat() + "Z",
                "message": payload.get("message"),
            }

    if normalization_error:
        return normalization_error
    return normalization_log


def _summary_log(job: Job) -> tuple[JobLog | None, dict[str, Any] | None]:
    for log in reversed(job.logs):
        try:
            payload = json.loads(log.content)
        except json.JSONDecodeError:
            continue
        if payload.get("kind") == "summary":
            return log, payload
    return None, None


def _job_payload(job: Job) -> dict[str, Any]:
    payload = job.to_dict()
    payload.update(
        {
            "type": job.type,
            "trigger": "manual",
            "user": job.user.email if job.user else None,
            "logSummary": _job_recent_logs(job),
        }
    )
    normalization = _job_normalization(job)
    if normalization:
        payload["normalization"] = normalization
    if job.error:
        payload["error"] = job.error
    return payload


def _job_log_payload(job: Job) -> dict[str, Any]:
    summary_log, summary_payload = _summary_log(job)
    payload = {
        "jobId": job.id,
        "type": job.type,
        "status": job.status,
        "startedAt": job.started_at.isoformat() + "Z" if job.started_at else None,
        "finishedAt": job.finished_at.isoformat() + "Z" if job.finished_at else None,
        "durationSec": job.duration_sec,
        "inserted": job.inserted,
        "updated": job.updated,
        "ignored": job.ignored,
        "errors": job.errors,
        "errorSummary": job.error,
        "logId": summary_log.id if summary_log else None,
        "totals": summary_payload.get("totals") if summary_payload else None,
    }
    normalization = _job_normalization(job)
    if normalization:
        payload["normalization"] = normalization
    payload = {key: value for key, value in payload.items() if value is not None}
    return payload


@bp.post("/importacoes/<string:tipo>/run")
@auth_required
def run_import(tipo: str):
    if tipo not in VALID_IMPORT_TYPES:
        return json_error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    try:
        job = enqueue_import(tipo=tipo, tenant_id=tenant_id, user_id=user.id)
    except (RuntimeError, ValueError) as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    return (
        jsonify(
            {
                "jobId": job.id,
                "status": job.status,
            }
        ),
        HTTPStatus.ACCEPTED,
    )


@bp.get("/jobs/<int:job_id>/status")
@auth_required
def job_status(job_id: int):
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    job = Job.query.filter_by(id=job_id, tenant_id=tenant_id, user_id=user.id).first()
    if not job:
        return json_error("Job não encontrado", HTTPStatus.NOT_FOUND)

    payload = job.to_dict()
    return jsonify(payload), HTTPStatus.OK


@bp.get("/jobs/<int:job_id>")
@auth_required
def job_detail(job_id: int):
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    job = (
        Job.query.options(joinedload(Job.logs), joinedload(Job.user))
        .filter_by(id=job_id, tenant_id=tenant_id, user_id=user.id)
        .first()
    )
    if not job:
        return json_error("Job não encontrado", HTTPStatus.NOT_FOUND)

    payload = _job_payload(job)
    payload["createdAt"] = job.created_at.isoformat() + "Z"
    payload["logCount"] = len(job.logs)
    return jsonify(payload), HTTPStatus.OK


@bp.get("/jobs/<int:job_id>/logs")
@auth_required
def job_logs(job_id: int):
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    job = Job.query.filter_by(id=job_id, tenant_id=tenant_id, user_id=user.id).first()
    if not job:
        return json_error("Job não encontrado", HTTPStatus.NOT_FOUND)

    after_param = request.args.get("after")
    try:
        after_id = int(after_param) if after_param is not None else None
    except ValueError:
        return json_error("Parâmetro 'after' inválido", HTTPStatus.BAD_REQUEST)

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return json_error("Parâmetro 'limit' inválido", HTTPStatus.BAD_REQUEST)

    limit = max(min(limit, 200), 1)

    query = JobLog.query.filter_by(job_id=job.id)
    if after_id is not None:
        query = query.filter(JobLog.id > after_id)

    logs = query.order_by(JobLog.id.asc()).limit(limit + 1).all()
    has_more = len(logs) > limit
    if has_more:
        logs = logs[:limit]

    items = [_parse_log_content(log) for log in logs]
    next_after = items[-1]["id"] if items else after_id

    return (
        jsonify({"items": items, "hasMore": has_more, "nextAfter": next_after}),
        HTTPStatus.OK,
    )


@bp.get("/importacoes/<string:tipo>")
@auth_required
def list_imports(tipo: str):
    if tipo not in VALID_IMPORT_TYPES:
        return json_error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(min(int(request.args.get("pageSize", 20)), 100), 1)

    query = (
        Job.query.options(joinedload(Job.logs), joinedload(Job.user))
        .filter_by(tenant_id=tenant_id, type=tipo, user_id=user.id)
        .order_by(Job.created_at.desc())
    )
    total = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [_job_payload(job) for job in jobs]
    return (
        jsonify(
            {
                "items": items,
                "page": page,
                "pageSize": page_size,
                "total": total,
            }
        ),
        HTTPStatus.OK,
    )


@bp.get("/logs")
@auth_required
def list_logs():
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    job_type = request.args.get("type")
    status = request.args.get("status")

    if job_type and job_type not in VALID_IMPORT_TYPES:
        return json_error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)
    if status and status not in {JobStatus.FINISHED, JobStatus.FAILED, JobStatus.RUNNING, JobStatus.QUEUED}:
        return json_error("Status de job inválido", HTTPStatus.BAD_REQUEST)

    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(min(int(request.args.get("pageSize", 20)), 100), 1)

    query = Job.query.options(joinedload(Job.logs)).filter_by(tenant_id=tenant_id, user_id=user.id)
    if job_type:
        query = query.filter(Job.type == job_type)
    if status:
        query = query.filter(Job.status == status)

    query = query.order_by(Job.finished_at.desc().nullslast(), Job.created_at.desc())

    total = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [_job_log_payload(job) for job in jobs]

    return (
        jsonify(
            {
                "items": items,
                "filters": {key: value for key, value in {"type": job_type, "status": status}.items() if value},
                "page": page,
                "pageSize": page_size,
                "total": total,
            }
        ),
        HTTPStatus.OK,
    )


@bp.get("/logs/<int:log_id>")
@auth_required
def log_details(log_id: int):
    tenant_id, user, error = _resolve_scope(None, allow_override=True)
    if error:
        return error
    assert tenant_id is not None and user is not None

    log = (
        JobLog.query.join(Job)
        .filter(JobLog.id == log_id, Job.tenant_id == tenant_id, Job.user_id == user.id)
        .first()
    )
    if not log:
        return json_error("Log não encontrado", HTTPStatus.NOT_FOUND)

    payload = _parse_log_content(log)
    payload.update({"jobId": log.job_id})
    return jsonify(payload), HTTPStatus.OK
