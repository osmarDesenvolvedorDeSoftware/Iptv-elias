from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class Bouquet(db.Model):
    __tablename__ = "bouquets"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    items = db.relationship(
        "BouquetItem",
        backref="bouquet",
        lazy=True,
        order_by="BouquetItem.created_at",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "name", name="uq_bouquets_tenant_name"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}

    def __repr__(self) -> str:
        return f"<Bouquet {self.id} tenant={self.tenant_id}>"


class BouquetItem(db.Model):
    __tablename__ = "bouquet_items"

    id = db.Column(db.Integer, primary_key=True)
    bouquet_id = db.Column(db.Integer, db.ForeignKey("bouquets.id"), nullable=False)
    content_id = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    source_tag = db.Column(db.String(255), nullable=True)
    source_tag_filmes = db.Column(db.String(255), nullable=True)
    metadata_json = db.Column("metadata", db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("bouquet_id", "content_id", name="uq_bouquet_items_unique"),
    )

    def as_catalog_item(self) -> dict[str, Any]:
        metadata = self.metadata_json or {}
        payload: dict[str, Any] = {
            "id": self.content_id,
            "type": self.type,
            "title": self.title,
        }
        if self.source_tag:
            payload["source_tag"] = self.source_tag
        if self.source_tag_filmes:
            payload["source_tag_filmes"] = self.source_tag_filmes
        if isinstance(metadata, dict):
            payload.update(metadata)
        return payload

    def __repr__(self) -> str:
        return f"<BouquetItem {self.id} bouquet={self.bouquet_id} content={self.content_id}>"
