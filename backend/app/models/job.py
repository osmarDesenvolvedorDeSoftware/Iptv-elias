from datetime import datetime

from ..extensions import db


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


class Job(db.Model):
    __tablename__ = "jobs"

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    logs = db.relationship("JobLog", backref="job", lazy=True)

    def to_dict(self) -> dict:
        payload = {
            "id": self.id,
            "status": self.status,
            "progress": self.progress if self.progress is not None else None,
            "etaSec": self.eta_sec,
        }
        if payload.get("progress") is None:
            payload.pop("progress", None)
        if payload.get("etaSec") is None:
            payload.pop("etaSec", None)
        return payload

    def __repr__(self) -> str:
        return f"<Job {self.id} {self.type} {self.status}>"
