from datetime import datetime

from ..extensions import db


class JobLog(db.Model):
    __tablename__ = "job_logs"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "jobId": self.job_id,
            "createdAt": self.created_at.isoformat() + "Z",
            "content": self.content,
        }

    def __repr__(self) -> str:
        return f"<JobLog {self.id} job={self.job_id}>"
