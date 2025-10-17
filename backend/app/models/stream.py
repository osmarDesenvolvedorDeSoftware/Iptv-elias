from __future__ import annotations

from datetime import datetime
from typing import Any

from ..extensions import db


class Stream(db.Model):
    __tablename__ = "streams"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    type = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(255), nullable=True)
    group_title = db.Column(db.String(255), nullable=True)
    is_adult = db.Column(db.Boolean, nullable=False, default=False)
    stream_source = db.Column(db.JSON, nullable=False)
    primary_url = db.Column(db.String(1024), nullable=False)
    target_container = db.Column(db.String(16), nullable=True)
    source_tag = db.Column(db.String(255), nullable=True)
    source_tag_filmes = db.Column(db.String(255), nullable=True)
    tmdb_id = db.Column(db.Integer, nullable=True)
    movie_properties = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "primary_url", name="uq_streams_tenant_url"),
        db.Index("ix_streams_tenant_type", "tenant_id", "type"),
        db.Index("ix_streams_source_tag", "source_tag"),
        db.Index("ix_streams_source_tag_filmes", "source_tag_filmes"),
    )

    episodes = db.relationship(
        "StreamEpisode",
        backref="stream",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def as_catalog_item(self) -> dict[str, Any]:
        metadata = self.movie_properties or {}
        item: dict[str, Any] = {
            "id": f"f_{self.id}",
            "type": "movie" if self.type == 2 else "stream",
            "title": self.title,
            "adult": self.is_adult,
            "source_tag": self.source_tag,
            "source_tag_filmes": self.source_tag_filmes,
            "source_domain": metadata.get("source_domain"),
        }
        for key in ("year", "genres", "poster", "backdrop", "rating", "overview", "runtime"):
            if metadata.get(key) is not None:
                item[key] = metadata.get(key)
        return item


class StreamSeries(db.Model):
    __tablename__ = "streams_series"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    title_base = db.Column(db.String(255), nullable=False)
    source_tag = db.Column(db.String(255), nullable=True)
    tmdb_id = db.Column(db.Integer, nullable=True)
    overview = db.Column(db.Text, nullable=True)
    poster = db.Column(db.String(512), nullable=True)
    backdrop = db.Column(db.String(512), nullable=True)
    rating = db.Column(db.Float, nullable=True)
    genres = db.Column(db.JSON, nullable=True)
    seasons = db.Column(db.Integer, nullable=True)
    is_adult = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    episodes = db.relationship(
        "StreamEpisode",
        backref="series",
        lazy=True,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("tenant_id", "title_base", "source_tag", name="uq_series_identity"),
        db.Index("ix_streams_series_source_tag", "source_tag"),
    )

    def as_catalog_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": f"s_{self.id}",
            "type": "series",
            "title": self.title,
            "adult": self.is_adult,
            "source_tag": self.source_tag,
        }
        metadata = {
            "genres": self.genres or [],
            "poster": self.poster,
            "backdrop": self.backdrop,
            "rating": self.rating,
            "overview": self.overview,
            "seasons": self.seasons,
        }
        for key, value in metadata.items():
            if value is not None:
                item[key] = value
        return item


class StreamEpisode(db.Model):
    __tablename__ = "streams_episodes"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(64), db.ForeignKey("tenants.id"), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey("streams.id"), nullable=False, unique=True)
    series_id = db.Column(db.Integer, db.ForeignKey("streams_series.id"), nullable=False)
    season = db.Column(db.Integer, nullable=False)
    episode = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index("ix_streams_episodes_series", "series_id"),
    )

    def __repr__(self) -> str:
        return f"<StreamEpisode series={self.series_id} S{self.season:02d}E{self.episode:02d}>"
