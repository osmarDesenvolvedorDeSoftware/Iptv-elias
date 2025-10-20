from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class TenantIntegrationConfig(db.Model):
    __tablename__ = "tenant_integration_configs"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False, unique=True)
    xui_db_uri = db.Column(db.String(512), nullable=True)
    xtream_base_url = db.Column(db.String(512), nullable=True)
    xtream_username = db.Column(db.String(128), nullable=True)
    xtream_password = db.Column(db.String(256), nullable=True)
    options = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self, include_secret: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tenantId": self.tenant_id,
            "xuiDbUri": self.xui_db_uri,
            "xtreamBaseUrl": self.xtream_base_url,
            "xtreamUsername": self.xtream_username,
            "options": self.options or {},
            "hasXtreamPassword": bool(self.xtream_password),
        }
        if include_secret:
            payload["xtreamPassword"] = self.xtream_password
        return payload

    def __repr__(self) -> str:
        return f"<TenantIntegrationConfig tenant={self.tenant_id}>"
