from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class Configuration(db.Model):
    __tablename__ = "configurations"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False, unique=True)
    data = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "tenant_id": self.tenant_id, "data": self.data}

    def __repr__(self) -> str:
        return f"<Configuration tenant={self.tenant_id}>"
