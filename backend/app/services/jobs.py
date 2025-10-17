
from ..extensions import db
from ..models import Job, JobStatus


def enqueue_import(tipo: str, tenant_id: str, user_id: int) -> Job:
    job = Job(
        tenant_id=tenant_id,
        user_id=user_id,
        type=tipo,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.session.add(job)
    db.session.commit()

    from ..tasks.importers import run_import

    run_import.delay(job_id=job.id, tipo=tipo, tenant_id=tenant_id, user_id=user_id)
    return job
