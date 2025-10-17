from __future__ import annotations

import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Bouquet, BouquetItem, Stream, StreamSeries

_CATALOG_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 300
_TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
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


def _movie_catalog_items(tenant_id: str) -> OrderedDict[str, dict[str, Any]]:
    catalog: OrderedDict[str, dict[str, Any]] = OrderedDict()
    movies = (
        Stream.query.filter_by(tenant_id=tenant_id, type=2)
        .order_by(Stream.created_at.desc())
        .all()
    )
    for movie in movies:
        payload = movie.as_catalog_item()
        payload["type"] = "movie"
        properties = movie.movie_properties or {}
        payload.setdefault("genres", properties.get("genres") or [])
        payload.setdefault("year", properties.get("year"))
        poster = payload.get("poster") or properties.get("poster")
        payload["poster"] = _normalize_poster_path(poster) or ""
        payload.setdefault("adult", movie.is_adult)
        payload.setdefault("source_domain", properties.get("source_domain"))
        runtime = properties.get("runtime")
        if runtime and "runtime" not in payload:
            payload["runtime"] = runtime
        catalog[payload["id"]] = payload
    return catalog


def _series_catalog_items(tenant_id: str) -> OrderedDict[str, dict[str, Any]]:
    catalog: OrderedDict[str, dict[str, Any]] = OrderedDict()
    series_list = (
        StreamSeries.query.options(joinedload(StreamSeries.episodes))
        .filter_by(tenant_id=tenant_id)
        .order_by(StreamSeries.created_at.desc())
        .all()
    )
    for series in series_list:
        payload = series.as_catalog_item()
        payload["poster"] = _normalize_poster_path(payload.get("poster") or series.poster) or ""
        payload.setdefault("genres", series.genres or [])
        payload.setdefault("adult", series.is_adult)
        if not payload.get("seasons"):
            seasons = {episode.season for episode in series.episodes}
            payload["seasons"] = len(seasons)
        catalog[payload["id"]] = payload
    return catalog


def _catalog_from_db(tenant_id: str) -> list[dict[str, Any]]:
    catalog: OrderedDict[str, dict[str, Any]] = OrderedDict()
    catalog.update(_movie_catalog_items(tenant_id))
    catalog.update(_series_catalog_items(tenant_id))

    saved_items = (
        BouquetItem.query.join(Bouquet)
        .filter(Bouquet.tenant_id == tenant_id)
        .order_by(BouquetItem.created_at.desc())
        .all()
    )
    for item in saved_items:
        payload = item.as_catalog_item()
        payload["poster"] = _normalize_poster_path(payload.get("poster")) or payload.get("poster") or ""
        existing = catalog.get(payload["id"]) or {}
        existing.update({k: v for k, v in payload.items() if v is not None})
        catalog[payload["id"]] = existing or payload

    return list(catalog.values())


def _invalidate_catalog_cache(tenant_id: str) -> None:
    _CATALOG_CACHE.pop(tenant_id, None)


def invalidate_catalog_cache(tenant_id: str) -> None:
    _invalidate_catalog_cache(tenant_id)


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
