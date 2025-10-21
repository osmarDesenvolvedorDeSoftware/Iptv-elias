from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("tenant_id", "key", name="uq_settings_tenant_key"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Setting tenant={self.tenant_id} key={self.key}>"
