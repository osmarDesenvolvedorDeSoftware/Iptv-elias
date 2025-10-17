from __future__ import annotations

import json
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Bouquet, BouquetItem, Job, JobLog

_CATALOG_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 300
_TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
_JOB_TYPE_TO_CONTENT_TYPE = {
    "filmes": "movie",
    "series": "series",
}
_CONTENT_PREFIX = {
    "movie": "f_",
    "series": "s_",
}


def _normalize_poster_path(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{_TMDB_IMAGE_BASE}{path}"


def _metadata_from_catalog(item: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "year",
        "genres",
        "poster",
        "seasons",
        "status",
        "runtime",
        "overview",
        "adult",
        "source_domain",
    }
    metadata = {key: item.get(key) for key in allowed_keys if item.get(key) is not None}
    return metadata


def list_bouquets(tenant_id: str) -> list[Bouquet]:
    return Bouquet.query.filter_by(tenant_id=tenant_id).order_by(Bouquet.created_at.asc()).all()


def _load_items_for_catalog(items: Iterable[BouquetItem]) -> OrderedDict[str, dict[str, Any]]:
    catalog: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in items:
        payload = item.as_catalog_item()
        payload["poster"] = _normalize_poster_path(payload.get("poster")) or ""
        if payload.get("type") == "series":
            payload.setdefault("seasons", 0)
            payload.setdefault("status", "indefinido")
        catalog[payload["id"]] = payload
    return catalog


def _load_recent_imports(tenant_id: str) -> OrderedDict[str, dict[str, Any]]:
    catalog: OrderedDict[str, dict[str, Any]] = OrderedDict()
    logs = (
        JobLog.query.options(joinedload(JobLog.job))
        .join(Job)
        .filter(Job.tenant_id == tenant_id)
        .order_by(JobLog.created_at.desc())
        .limit(500)
        .all()
    )
    for log in logs:
        try:
            payload = log.content
            if isinstance(payload, str):
                payload = json.loads(payload)
        except Exception:  # pragma: no cover - resilient to malformed logs
            continue

        if not isinstance(payload, dict) or payload.get("kind") != "item":
            continue

        job = log.job
        content_type = payload.get("type") or (job and _JOB_TYPE_TO_CONTENT_TYPE.get(job.type))
        if content_type not in _CONTENT_PREFIX:
            continue
        tmdb_id = payload.get("tmdb_id")
        if not tmdb_id:
            continue

        content_id = f"{_CONTENT_PREFIX[content_type]}{tmdb_id}"
        if content_id in catalog:
            continue

        title = payload.get("title")
        if not title:
            continue

        item: dict[str, Any] = {
            "id": content_id,
            "type": content_type,
            "title": title,
            "year": payload.get("year"),
            "genres": payload.get("genres") or [],
            "adult": payload.get("adult", False),
            "source_tag": payload.get("source_tag"),
            "source_tag_filmes": payload.get("source_tag_filmes"),
        }
        if content_type == "series":
            item["seasons"] = payload.get("seasons") or 0
            series_status = payload.get("series_status")
            raw_status = payload.get("status")
            if not series_status and raw_status not in {None, "inserted", "error"}:
                series_status = raw_status
            item["status"] = series_status or "indefinido"
        else:
            item["poster"] = _normalize_poster_path(payload.get("poster")) or ""
            runtime = payload.get("runtime")
            if runtime:
                item["runtime"] = runtime
        overview = payload.get("overview")
        if overview:
            item["overview"] = overview
        poster = payload.get("poster") if content_type == "series" else None
        if content_type == "series":
            item["poster"] = _normalize_poster_path(poster) or ""
        source_domain = payload.get("source_domain")
        if source_domain:
            item["source_domain"] = source_domain
        catalog[content_id] = item
    return catalog


def _catalog_from_db(tenant_id: str) -> list[dict[str, Any]]:
    saved_items = (
        BouquetItem.query.join(Bouquet)
        .filter(Bouquet.tenant_id == tenant_id)
        .order_by(BouquetItem.created_at.desc())
        .all()
    )
    catalog = _load_items_for_catalog(saved_items)

    recent = _load_recent_imports(tenant_id)
    for content_id, item in recent.items():
        if content_id not in catalog:
            catalog[content_id] = item

    return list(catalog.values())


def _invalidate_catalog_cache(tenant_id: str) -> None:
    _CATALOG_CACHE.pop(tenant_id, None)


def get_catalog(tenant_id: str) -> list[dict[str, Any]]:
    cached = _CATALOG_CACHE.get(tenant_id)
    now = time.time()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    catalog = _catalog_from_db(tenant_id)
    catalog.sort(key=lambda item: (item.get("type", ""), item.get("title", "")))
    _CATALOG_CACHE[tenant_id] = (now, catalog)
    return catalog


def get_selections_map(tenant_id: str) -> dict[str, list[str]]:
    selections: dict[str, list[str]] = {}
    items = (
        BouquetItem.query.join(Bouquet)
        .filter(Bouquet.tenant_id == tenant_id)
        .order_by(BouquetItem.bouquet_id.asc(), BouquetItem.created_at.asc(), BouquetItem.id.asc())
        .all()
    )
    for item in items:
        selections.setdefault(str(item.bouquet_id), []).append(item.content_id)
    return selections


def create_bouquet(tenant_id: str, name: str) -> Bouquet:
    existing = Bouquet.query.filter_by(tenant_id=tenant_id, name=name).first()
    if existing:
        raise ValueError("Já existe um bouquet com este nome")

    bouquet = Bouquet(tenant_id=tenant_id, name=name)
    db.session.add(bouquet)
    db.session.commit()
    return bouquet


def update_bouquet_items(tenant_id: str, bouquet_id: int, content_ids: list[str]) -> datetime:
    bouquet = Bouquet.query.filter_by(id=bouquet_id, tenant_id=tenant_id).first()
    if not bouquet:
        raise LookupError("Bouquet não encontrado")

    catalog_map = {item["id"]: item for item in get_catalog(tenant_id)}
    existing_map = {item.content_id: item for item in bouquet.items}

    BouquetItem.query.filter_by(bouquet_id=bouquet.id).delete(synchronize_session=False)

    to_insert: list[BouquetItem] = []
    for content_id in content_ids:
        source = catalog_map.get(content_id)
        if not source:
            existing_item = existing_map.get(content_id)
            if existing_item:
                source = existing_item.as_catalog_item()
        if not source:
            continue

        metadata = _metadata_from_catalog(source)
        item = BouquetItem(
            bouquet_id=bouquet.id,
            content_id=content_id,
            type=source.get("type", "movie"),
            title=source.get("title") or content_id,
            source_tag=source.get("source_tag"),
            source_tag_filmes=source.get("source_tag_filmes"),
            metadata_json=metadata,
        )
        to_insert.append(item)

    if to_insert:
        db.session.bulk_save_objects(to_insert)
    db.session.commit()
    _invalidate_catalog_cache(tenant_id)

    return datetime.utcnow()
