
from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import Job, JobStatus, UserConfig
from .xui_integration import get_worker_config


def enqueue_import(tipo: str, tenant_id: str, user_id: int) -> Job:
    job = Job(
        tenant_id=tenant_id,
        user_id=user_id,
        type=tipo,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.session.add(job)

    config = UserConfig.query.filter_by(user_id=user_id).first()
    if config:
        config.last_sync = datetime.utcnow()

    worker_config = get_worker_config(tenant_id, user_id)
    uri = worker_config.get("xui_db_uri")
    if not uri:
        current_app.logger.error(
            "[jobs] Banco XUI ausente para tenant %s / usuário %s",
            tenant_id,
            user_id,
        )
        raise RuntimeError("Banco XUI não configurado para este usuário.")

    current_app.logger.info(
        "[jobs] Usando banco XUI %s para tenant %s / usuário %s",
        uri,
        tenant_id,
        user_id,
    )

    if not worker_config.get("xtream_base_url"):
        raise RuntimeError("URL do painel Xtream não configurada para este usuário.")
    if not worker_config.get("xtream_username") or not worker_config.get("xtream_password"):
        raise RuntimeError("Credenciais do painel Xtream não configuradas para este usuário.")
    db.session.commit()

    from ..tasks.importers import run_import

    run_import.delay(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job.id)
    return job
