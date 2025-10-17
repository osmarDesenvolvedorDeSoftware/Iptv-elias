from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.orm import joinedload

from ..models import Job, JobLog, JobStatus
from ..services.jobs import enqueue_import

bp = Blueprint("imports", __name__)

VALID_IMPORT_TYPES = {"filmes", "series"}


def _tenant_from_request():
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, _error("Cabeçalho X-Tenant-ID é obrigatório", HTTPStatus.BAD_REQUEST)
    identity = get_jwt_identity()
    if identity.get("tenant_id") != tenant_id:
        return None, _error("Tenant inválido para o usuário", HTTPStatus.FORBIDDEN)
    return tenant_id, None


def _error(message: str, status: HTTPStatus):
    response = jsonify({"message": message})
    response.status_code = status
    return response


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
    payload = {key: value for key, value in payload.items() if value is not None}
    return payload


@bp.post("/importacoes/<string:tipo>/run")
@jwt_required()
def run_import(tipo: str):
    if tipo not in VALID_IMPORT_TYPES:
        return _error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, error = _tenant_from_request()
    if error:
        return error

    identity = get_jwt_identity()
    job = enqueue_import(tipo=tipo, tenant_id=tenant_id, user_id=identity["user_id"])

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
@jwt_required()
def job_status(job_id: int):
    tenant_id, error = _tenant_from_request()
    if error:
        return error

    job = Job.query.filter_by(id=job_id, tenant_id=tenant_id).first()
    if not job:
        return _error("Job não encontrado", HTTPStatus.NOT_FOUND)

    payload = job.to_dict()
    return jsonify(payload), HTTPStatus.OK


@bp.get("/importacoes/<string:tipo>")
@jwt_required()
def list_imports(tipo: str):
    if tipo not in VALID_IMPORT_TYPES:
        return _error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, error = _tenant_from_request()
    if error:
        return error

    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(min(int(request.args.get("pageSize", 20)), 100), 1)

    query = (
        Job.query.options(joinedload(Job.logs), joinedload(Job.user))
        .filter_by(tenant_id=tenant_id, type=tipo)
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
@jwt_required()
def list_logs():
    tenant_id, error = _tenant_from_request()
    if error:
        return error

    job_type = request.args.get("type")
    status = request.args.get("status")

    if job_type and job_type not in VALID_IMPORT_TYPES:
        return _error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)
    if status and status not in {JobStatus.FINISHED, JobStatus.FAILED, JobStatus.RUNNING, JobStatus.QUEUED}:
        return _error("Status de job inválido", HTTPStatus.BAD_REQUEST)

    page = max(int(request.args.get("page", 1)), 1)
    page_size = max(min(int(request.args.get("pageSize", 20)), 100), 1)

    query = Job.query.options(joinedload(Job.logs)).filter_by(tenant_id=tenant_id)
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
@jwt_required()
def log_details(log_id: int):
    tenant_id, error = _tenant_from_request()
    if error:
        return error

    log = JobLog.query.join(Job).filter(JobLog.id == log_id, Job.tenant_id == tenant_id).first()
    if not log:
        return _error("Log não encontrado", HTTPStatus.NOT_FOUND)

    payload = _parse_log_content(log)
    payload.update({"jobId": log.job_id})
    return jsonify(payload), HTTPStatus.OK
