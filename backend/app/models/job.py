from datetime import datetime

from ..extensions import db


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class Job(db.Model):
    __tablename__ = "jobs"
    __table_args__ = (
        db.Index("ix_jobs_tenant_type_started", "tenant_id", "type", "started_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=JobStatus.QUEUED)
    progress = db.Column(db.Float, nullable=False, default=0.0)
    eta_sec = db.Column(db.Integer, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.Text, nullable=True)
    inserted = db.Column(db.Integer, nullable=False, default=0)
    updated = db.Column(db.Integer, nullable=False, default=0)
    ignored = db.Column(db.Integer, nullable=False, default=0)
    errors = db.Column(db.Integer, nullable=False, default=0)
    duration_sec = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    logs = db.relationship("JobLog", backref="job", lazy=True, order_by="JobLog.created_at")

    def to_dict(self) -> dict:
        payload: dict[str, object] = {
            "id": self.id,
            "status": self.status,
        }
        if self.progress is not None:
            payload["progress"] = self.progress
        if self.eta_sec is not None:
            payload["etaSec"] = self.eta_sec
        if self.inserted is not None:
            payload["inserted"] = self.inserted
        if self.updated is not None:
            payload["updated"] = self.updated
        if self.ignored is not None:
            payload["ignored"] = self.ignored
        if self.errors is not None:
            payload["errors"] = self.errors
        if self.duration_sec is not None:
            payload["durationSec"] = self.duration_sec
        if self.started_at:
            payload["startedAt"] = self.started_at.isoformat() + "Z"
        if self.finished_at:
            payload["finishedAt"] = self.finished_at.isoformat() + "Z"
        return payload

    def __repr__(self) -> str:
        return f"<Job {self.id} {self.type} {self.status}>"
