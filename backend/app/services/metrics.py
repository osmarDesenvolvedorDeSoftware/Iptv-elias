from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func

from ..extensions import db
from ..models import Job, JobStatus


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    value = value.replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")


def get_dashboard_metrics(tenant_id: str) -> dict[str, int | str | None]:
    type_counts = dict(
        db.session.query(Job.type, func.count(Job.id))
        .filter(Job.tenant_id == tenant_id)
        .group_by(Job.type)
        .all()
    )

    movies = int(type_counts.get("filmes", 0) or 0)
    series = int(type_counts.get("series", 0) or 0)
    imports_total = int(sum(type_counts.values()) if type_counts else 0)

    failed_jobs = (
        db.session.query(func.count(Job.id))
        .filter(Job.tenant_id == tenant_id, Job.status == JobStatus.FAILED)
        .scalar()
        or 0
    )

    last_import_at = (
        db.session.query(func.max(Job.finished_at))
        .filter(Job.tenant_id == tenant_id, Job.finished_at.isnot(None))
        .scalar()
    )

    return {
        "movies": movies,
        "series": series,
        "imports": imports_total,
        "failed_jobs": int(failed_jobs),
        "last_import_at": _format_datetime(last_import_at),
    }
