
from datetime import datetime

from ..extensions import db
from ..models import Job, JobStatus, UserConfig


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
    db.session.commit()

    from ..tasks.importers import run_import

    run_import.delay(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job.id)
    return job
