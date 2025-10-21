from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class UserConfig(db.Model):
    __tablename__ = "user_configs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    domain = db.Column("dominio", db.String(255), nullable=True)
    port = db.Column("porta", db.Integer, nullable=True)
    api_username = db.Column("usuario_api", db.String(255), nullable=True)
    api_password = db.Column("senha_api", db.String(512), nullable=True)
    xui_db_uri = db.Column(db.String(512), nullable=True)
    active = db.Column("ativo", db.Boolean, nullable=False, default=True)
    last_sync = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self, include_secret: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "domain": self.domain,
            "port": self.port,
            "username": self.api_username,
            "active": self.active,
            "lastSync": self.last_sync.isoformat() + "Z" if self.last_sync else None,
            "hasPassword": bool(self.api_password),
            "xuiDbUri": getattr(self, "resolved_xui_db_uri", self.xui_db_uri),
        }
        if include_secret:
            payload["password"] = self.api_password
        return payload

    def __repr__(self) -> str:
        return f"<UserConfig user={self.user_id}>"
