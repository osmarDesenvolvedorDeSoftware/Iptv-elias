from datetime import datetime

from ..extensions import db


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship("User", backref="tenant", lazy=True)
    jobs = db.relationship("Job", backref="tenant", lazy=True)

    def __repr__(self) -> str:
        return f"<Tenant {self.id}>"
