from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.JSON, nullable=False, default=dict)
    db_host = db.Column(db.String(255), nullable=True)
    db_port = db.Column(db.Integer, nullable=True)
    db_user = db.Column(db.String(255), nullable=True)
    db_password = db.Column(db.String(512), nullable=True)
    db_name = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref(
            "settings",
            lazy=True,
            cascade="all, delete-orphan",
            passive_deletes=True,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "user_id", "key", name="uq_settings_tenant_user_key"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "key": self.key,
            "value": self.value,
            "db_host": self.db_host,
            "db_port": self.db_port,
            "db_user": self.db_user,
            "db_name": self.db_name,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Setting tenant={self.tenant_id} key={self.key}>"
