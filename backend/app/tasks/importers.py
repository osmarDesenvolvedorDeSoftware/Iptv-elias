import time
from datetime import datetime

from ..extensions import celery_app, db
from ..models import Job, JobLog, JobStatus


@celery_app.task(name="tasks.run_import")
def run_import(job_id: int, tipo: str, tenant_id: str, user_id: int):
    job: Job | None = Job.query.filter_by(id=job_id, tenant_id=tenant_id, user_id=user_id).first()
    if not job:
        return

    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    job.error = None
    db.session.commit()

    total_steps = 10
    step_delay = 0.5

    try:
        for step in range(1, total_steps + 1):
            time.sleep(step_delay)
            progress = step / total_steps
            job.progress = progress
            job.eta_sec = int((total_steps - step) * step_delay)
            db.session.commit()

        job.status = JobStatus.FINISHED
        job.progress = 1.0
        job.finished_at = datetime.utcnow()
        job.eta_sec = None
        db.session.add(
            JobLog(
                job_id=job.id,
                content=f"Importação de {tipo} concluída com sucesso",
            )
        )
        db.session.commit()
    except Exception as exc:  # pragma: no cover - defensive
        db.session.rollback()
        job = Job.query.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = datetime.utcnow()
            job.eta_sec = None
            db.session.add(
                JobLog(job_id=job.id, content=f"Importação de {tipo} falhou: {exc}")
            )
            db.session.commit()
        raise
