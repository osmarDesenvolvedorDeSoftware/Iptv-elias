
from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import Job, JobStatus, UserConfig
from .user_configs import resolve_xui_db_uri


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
        uri = resolve_xui_db_uri(config)
        if uri:
            current_app.logger.info(
                "[jobs] XUI DB URI detectado para tenant %s / usuário %s: %s",
                tenant_id,
                user_id,
                uri,
            )
        else:
            current_app.logger.warning(
                "[jobs] XUI DB URI não configurado para tenant %s / usuário %s",
                tenant_id,
                user_id,
            )
    db.session.commit()

    from ..tasks.importers import run_import

    run_import.delay(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job.id)
    return job
