"""Tarefas responsáveis por normalizar as origens do XUI."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import celery_app, db
from ..models import Job, JobLog
from ..services.xui_db import XuiCredentials, XuiRepository, get_engine
from ..services.xui_integration import get_worker_config
from ..services.xui_normalizer import NormalizationResult

logger = logging.getLogger(__name__)


def _build_repository(tenant_id: str) -> XuiRepository:
    worker_config = get_worker_config(tenant_id)
    uri = worker_config.get("xui_db_uri")
    if not uri:
        raise RuntimeError("xui_db_uri não configurado")
    engine = get_engine(tenant_id, None, XuiCredentials(uri))
    repository = XuiRepository(engine)
    repository.ensure_compatibility()
    return repository


def run_normalization(tenant_id: str) -> NormalizationResult:
    repository = _build_repository(tenant_id)
    return repository.normalize_sources()


def _persist_log(job: Job, payload: dict[str, Any]) -> None:
    try:
        db.session.add(JobLog(job_id=job.id, content=json.dumps(payload, ensure_ascii=False)))
        db.session.commit()
    except SQLAlchemyError:
        logger.exception("Falha ao persistir log de normalização para o job %s", job.id)
        db.session.rollback()
        raise


@celery_app.task(name="tasks.normalize_xui_sources")
def normalize_xui_sources(tenant_id: str, job_id: int | None = None) -> dict[str, Any]:
    result = run_normalization(tenant_id)

    if job_id is not None:
        job = Job.query.filter_by(id=job_id, tenant_id=tenant_id).first()
        if job is not None:
            payload = result.to_log_payload()
            _persist_log(job, payload)
        else:
            logger.warning("Job %s não encontrado para registrar normalização", job_id)

    return result.to_dict()


__all__ = ["normalize_xui_sources", "run_normalization"]
