"""Importadores Celery que sincronizam o catálogo diretamente no XUI."""

from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, TypeVar

import requests
from sqlalchemy.exc import SQLAlchemyError

from ..config import Config
from ..extensions import celery_app, db
from ..models import Job, JobLog, JobStatus
from ..services.importers import categoria_adulta, dominio_de, source_tag_from_url, target_container_from_url
from ..services.xui_db import XuiCredentials, XuiRepository, get_engine
from ..services.xui_integration import get_worker_config
from ..services.xui_normalizer import NormalizationResult
from ..services.xtream_client import XtreamClient, XtreamError

logger = logging.getLogger(__name__)

_IMPORT_TYPES = {"filmes", "series"}
_LOG_BATCH = 10
_CONFIG = Config()
_T = TypeVar("_T")


def _clean_option_str(value: Any) -> str | None:
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return None


def _sanitize_tmdb_query(title: str) -> str:
    if not isinstance(title, str):
        return ""
    sanitized = re.sub(r"\s*-\s*\d{4}$", "", title)
    sanitized = re.sub(r"\(\d{4}\)", "", sanitized)
    sanitized = re.sub(r"\s{2,}", " ", sanitized)
    return sanitized.strip()


def _parse_ignore_entry(entry: Any) -> dict[str, Any]:
    category_ids: set[str] = set()
    category_names: dict[str, str] = {}
    prefixes: list[tuple[str, str]] = []
    if isinstance(entry, Mapping):
        raw_categories = entry.get("categories")
        if isinstance(raw_categories, (list, tuple, set)):
            for item in raw_categories:
                if item is None:
                    continue
                value = str(item).strip()
                if not value:
                    continue
                category_ids.add(value)
                if not value.isdigit():
                    normalized = value.lower()
                    category_names.setdefault(normalized, value)
        raw_prefixes = entry.get("prefixes")
        if isinstance(raw_prefixes, (list, tuple, set)):
            for raw_prefix in raw_prefixes:
                if not isinstance(raw_prefix, str):
                    continue
                trimmed = raw_prefix.strip()
                if not trimmed:
                    continue
                prefixes.append((trimmed, trimmed.lower()))
    return {
        "category_ids": category_ids,
        "category_names": category_names,
        "prefixes": tuple(prefixes),
    }


def _ensure_job(tipo: str, tenant_id: str, user_id: int, job_id: int | None) -> Job:
    job: Job | None = None
    if job_id:
        job = Job.query.filter_by(id=job_id, tenant_id=tenant_id, user_id=user_id).first()
    if job is None:
        job = Job(tenant_id=tenant_id, user_id=user_id, type=tipo)
        db.session.add(job)
        db.session.commit()
    job.status = JobStatus.RUNNING
    job.progress = 0.0
    job.started_at = datetime.utcnow()
    job.finished_at = None
    job.error = None
    job.inserted = 0
    job.updated = 0
    job.ignored = 0
    job.errors = 0
    job.duration_sec = None
    job.eta_sec = None
    job.source_tag = None
    job.source_tag_filmes = None
    db.session.commit()
    return job


def _estimate_eta(start_time: datetime, processed: int, total: int) -> int | None:
    if processed <= 0 or total <= 0:
        return None
    remaining = max(total - processed, 0)
    if remaining == 0:
        return None
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    if elapsed <= 0:
        return None
    avg = elapsed / max(processed, 1)
    return int(max(avg * remaining, 0))


def _persist_logs(job: Job, buffer: list[dict[str, Any]]) -> None:
    if not buffer:
        return
    db.session.add_all(
        [JobLog(job_id=job.id, content=json.dumps(entry, ensure_ascii=False)) for entry in buffer]
    )
    db.session.flush()


def _log_normalization(job: Job, result: NormalizationResult) -> None:
    payload = result.to_log_payload()
    db.session.add(JobLog(job_id=job.id, content=json.dumps(payload, ensure_ascii=False)))
    db.session.commit()


def _build_tmdb_params(options: Mapping[str, Any]) -> dict[str, Any] | None:
    tmdb_opts = options.get("tmdb", {}) if isinstance(options, Mapping) else {}
    enabled = bool(tmdb_opts.get("enabled"))
    api_key = _clean_option_str(tmdb_opts.get("apiKey")) or _clean_option_str(_CONFIG.TMDB_API_KEY)
    if not enabled or not api_key:
        return None
    language = _clean_option_str(tmdb_opts.get("language")) or _clean_option_str(_CONFIG.TMDB_LANGUAGE)
    region = _clean_option_str(tmdb_opts.get("region")) or _clean_option_str(_CONFIG.TMDB_REGION)
    return {
        "api_key": api_key,
        "language": language or _CONFIG.TMDB_LANGUAGE,
        "region": region or _CONFIG.TMDB_REGION,
    }


def _fetch_tmdb_movie(title: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        query = _sanitize_tmdb_query(title)
        if not query:
            query = (title or "").strip()
        if not query:
            return {}
        response = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"query": query, **params, "page": 1, "include_adult": True},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return {}
        movie = results[0]
        return {
            "overview": movie.get("overview"),
            "poster": movie.get("poster_path"),
            "backdrop": movie.get("backdrop_path"),
            "genres": movie.get("genre_ids", []),
            "rating": movie.get("vote_average"),
            "release_date": movie.get("release_date"),
        }
    except requests.RequestException as exc:  # pragma: no cover - dependência externa
        logger.warning("TMDb indisponível para filme %s: %s", title, exc)
        return {}


def _fetch_tmdb_series(title: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        query = _sanitize_tmdb_query(title)
        if not query:
            query = (title or "").strip()
        if not query:
            return {}
        response = requests.get(
            "https://api.themoviedb.org/3/search/tv",
            params={"query": query, **params, "page": 1},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return {}
        series = results[0]
        return {
            "overview": series.get("overview"),
            "poster": series.get("poster_path"),
            "backdrop": series.get("backdrop_path"),
            "rating": series.get("vote_average"),
        }
    except requests.RequestException as exc:  # pragma: no cover - dependência externa
        logger.warning("TMDb indisponível para série %s: %s", title, exc)
        return {}


def _movie_properties(title: str, tmdb_payload: Mapping[str, Any], fallback_icon: str | None) -> dict[str, Any]:
    poster_path = tmdb_payload.get("poster")
    if poster_path and not poster_path.startswith("http"):
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
    else:
        poster_url = poster_path or fallback_icon or ""
    backdrop_path = tmdb_payload.get("backdrop")
    if backdrop_path and not backdrop_path.startswith("http"):
        backdrop_url = f"https://image.tmdb.org/t/p/w780{backdrop_path}"
    else:
        backdrop_url = backdrop_path or poster_url
    return {
        "name": title,
        "o_name": title,
        "cover_big": poster_url,
        "movie_image": poster_url,
        "release_date": tmdb_payload.get("release_date") or "",
        "youtube_trailer": "",
        "director": "",
        "actors": "",
        "cast": "",
        "description": "",
        "plot": tmdb_payload.get("overview") or "",
        "genre": ", ".join(map(str, tmdb_payload.get("genres", []))) if tmdb_payload.get("genres") else "",
        "backdrop_path": [backdrop_url] if backdrop_url else [],
        "duration_secs": 0,
        "duration": "00:00:00",
        "video": [],
        "audio": [],
        "bitrate": 0,
        "rating": tmdb_payload.get("rating") or "",
        "tmdb_id": "",
        "age": "",
        "mpaa_rating": "",
        "rating_count_kinopoisk": 0,
        "country": "",
        "kinopoisk_url": "",
    }


def _episode_properties(tmdb_payload: Mapping[str, Any], poster: str | None, season: int) -> dict[str, Any]:
    return {
        "release_date": "",
        "plot": tmdb_payload.get("overview") or "",
        "duration_secs": 0,
        "duration": "00:00:00",
        "movie_image": poster or "",
        "video": [],
        "audio": [],
        "bitrate": 0,
        "rating": tmdb_payload.get("rating") or "",
        "season": str(season),
        "tmdb_id": "",
        "genre": "",
        "actors": "",
        "youtube_trailer": "",
    }


def _is_adult(title: str, category_name: str | None, category_id: str | None, options: Mapping[str, Any]) -> bool:
    keywords = {kw.lower() for kw in options.get("adultKeywords", []) if isinstance(kw, str)}
    categories = {str(cid) for cid in options.get("adultCategories", [])}
    if category_id and str(category_id) in categories:
        return True
    if category_name and any(keyword in category_name.lower() for keyword in keywords):
        return True
    return categoria_adulta(title) or categoria_adulta(category_name)


def _normalize_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


class _BaseImporter:
    def __init__(
        self,
        *,
        job: Job,
        tenant_id: str,
        repository: XuiRepository,
        xtream: XtreamClient,
        options: Mapping[str, Any],
    ) -> None:
        self.job = job
        self.tenant_id = tenant_id
        self.repository = repository
        self.xtream = xtream
        self.options = options
        self.start_time = datetime.utcnow()
        self.buffer: list[dict[str, Any]] = []
        self.total_items = 0
        self.processed = 0
        self.inserted = 0
        self.updated = 0
        self.ignored = 0
        self.errors = 0
        self.domains: Counter[str] = Counter()
        ignore_opts = options.get("ignore") if isinstance(options, Mapping) else {}
        self._ignore_movies = _parse_ignore_entry(ignore_opts.get("movies") if isinstance(ignore_opts, Mapping) else None)
        self._ignore_series = _parse_ignore_entry(ignore_opts.get("series") if isinstance(ignore_opts, Mapping) else None)
        retry_opts = options.get("retry") if isinstance(options, Mapping) else {}
        retry_mapping = retry_opts if isinstance(retry_opts, Mapping) else {}
        self._retry_enabled = bool(retry_mapping.get("enabled", True))
        max_attempts_raw = retry_mapping.get("maxAttempts")
        backoff_raw = retry_mapping.get("backoffSeconds")
        self._retry_max_attempts = max(1, int(max_attempts_raw if max_attempts_raw is not None else 3))
        self._retry_backoff = max(1, int(backoff_raw if backoff_raw is not None else 5))
        self._write_throttle_ms = max(0, int(options.get("throttleMs") or 0)) if isinstance(options, Mapping) else 0
        self._max_parallel_writes = max(1, int(options.get("maxParallel") or 1)) if isinstance(options, Mapping) else 1
        self._write_counter = 0
        self._movie_cache: dict[str, Mapping[str, Any] | None] = {}
        self._episode_cache: dict[str, Mapping[str, Any] | None] = {}

    def _log(self, payload: Mapping[str, Any]) -> None:
        self.buffer.append(dict(payload))
        if len(self.buffer) >= _LOG_BATCH:
            _persist_logs(self.job, self.buffer)
            self.buffer.clear()

    def _commit(self) -> None:
        self.job.progress = (self.processed / self.total_items) if self.total_items else 1.0
        self.job.inserted = self.inserted
        self.job.updated = self.updated
        self.job.ignored = self.ignored
        self.job.errors = self.errors
        self.job.eta_sec = _estimate_eta(self.start_time, self.processed, self.total_items)
        db.session.commit()

    def finalize(self) -> None:
        if self.buffer:
            _persist_logs(self.job, self.buffer)
            self.buffer.clear()
        db.session.commit()

    def execute(self) -> None:
        raise NotImplementedError

    def _with_retry(self, func: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
        attempts = 0
        while True:
            attempts += 1
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - defensivo
                if not self._retry_enabled or attempts >= self._retry_max_attempts:
                    raise
                wait_time = self._retry_backoff * attempts
                logger.warning(
                    "Operação %s falhou (tentativa %s/%s): %s",
                    getattr(func, "__name__", repr(func)),
                    attempts,
                    self._retry_max_attempts,
                    exc,
                )
                time.sleep(wait_time)

    def _apply_write_throttle(self) -> None:
        if self._write_throttle_ms <= 0:
            return
        self._write_counter += 1
        if self._write_counter >= self._max_parallel_writes:
            time.sleep(self._write_throttle_ms / 1000)
            self._write_counter = 0

    def _should_ignore(
        self,
        kind: str,
        title: str,
        category_id: str | None,
        category_name: str | None,
    ) -> dict[str, str] | None:
        rules = self._ignore_movies if kind == "movies" else self._ignore_series
        cat_id = (category_id or "").strip()
        cat_name = (category_name or "").strip()
        if cat_id and cat_id in rules["category_ids"]:
            return {"type": "categoryId", "value": cat_id}
        if cat_name:
            normalized = cat_name.lower()
            if normalized in rules["category_names"]:
                return {"type": "categoryName", "value": rules["category_names"][normalized]}
        title_clean = (title or "").strip()
        if not title_clean:
            return None
        title_lower = title_clean.lower()
        for raw_prefix, normalized_prefix in rules["prefixes"]:
            if title_lower.startswith(normalized_prefix):
                return {"type": "prefix", "value": raw_prefix}
        return None

    def _get_cached_movie(self, url: str) -> Mapping[str, Any] | None:
        if url not in self._movie_cache:
            self._movie_cache[url] = self._with_retry(self.repository.movie_url_exists, url)
        return self._movie_cache[url]

    def _cache_movie(self, url: str, payload: Mapping[str, Any] | None) -> None:
        self._movie_cache[url] = payload

    def _get_cached_episode(self, url: str) -> Mapping[str, Any] | None:
        if url not in self._episode_cache:
            self._episode_cache[url] = self._with_retry(self.repository.episode_url_exists, url)
        return self._episode_cache[url]

    def _cache_episode(self, url: str, payload: Mapping[str, Any] | None) -> None:
        self._episode_cache[url] = payload


class _MovieImporter(_BaseImporter):
    def execute(self) -> None:
        data = self.xtream.vod_streams()
        limit = _normalize_int(self.options.get("limitItems"))
        if limit and limit > 0:
            data = data[:limit]
        mapping = (self.options.get("categoryMapping", {}) or {}).get("movies", {})
        tmdb_params = _build_tmdb_params(self.options)
        tmdb_language = None
        if isinstance(tmdb_params, Mapping):
            tmdb_language = tmdb_params.get("language")
        tmdb_language = tmdb_language or _CONFIG.TMDB_LANGUAGE
        bouquets = self.options.get("bouquets", {}) or {}
        movies_bouquet = bouquets.get("movies")
        adult_bouquet = bouquets.get("adult")

        self.total_items = len(data)
        categories_by_id = {str(cat.get("category_id")): cat.get("category_name") for cat in self.xtream.vod_categories()}

        for entry in data:
            try:
                stream_id = entry.get("stream_id")
                title = (entry.get("name") or "").strip()
                category_id = str(entry.get("category_id")) if entry.get("category_id") is not None else None
                category_name = categories_by_id.get(category_id) or entry.get("category_name")
                icon = entry.get("stream_icon")
                extension = (entry.get("container_extension") or "mp4").strip()
                if not title or not stream_id:
                    self.processed += 1
                    self.ignored += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "ignored",
                            "title": title or str(stream_id),
                            "reason": "missing-data",
                        }
                    )
                    self._commit()
                    continue

                ignore_info = self._should_ignore("movies", title, category_id, category_name)
                if ignore_info:
                    self.processed += 1
                    self.ignored += 1
                    log_payload = {
                        "kind": "item",
                        "status": "ignored",
                        "title": title,
                        "reason": f"ignored-{ignore_info['type']}",
                    }
                    if category_id:
                        log_payload["categoryId"] = category_id
                    if category_name:
                        log_payload["categoryName"] = category_name
                    if ignore_info["type"] == "prefix":
                        log_payload["prefix"] = ignore_info["value"]
                    self._log(log_payload)
                    self._commit()
                    continue

                xui_category = mapping.get(str(category_id)) if isinstance(mapping, dict) else None
                xui_category_id = _normalize_int(xui_category)
                if xui_category_id is None:
                    self.processed += 1
                    self.ignored += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "ignored",
                            "title": title,
                            "reason": "missing-category-mapping",
                            "categoryId": category_id,
                        }
                    )
                    self._commit()
                    continue

                url = f"{self.xtream.base_url}/movie/{self.xtream.username}/{self.xtream.password}/{stream_id}.{extension}"
                tmdb_payload = _fetch_tmdb_movie(title, tmdb_params) if tmdb_params else {}
                properties = _movie_properties(title, tmdb_payload, icon)
                is_adult = _is_adult(title, category_name, category_id, self.options)
                target_container = target_container_from_url(url)
                source_tag = source_tag_from_url(url)
                existing = self._get_cached_movie(url)
                if existing:
                    existing_id_raw = existing.get("id") if isinstance(existing, Mapping) else None
                    try:
                        existing_id = int(existing_id_raw) if existing_id_raw is not None else None
                    except (TypeError, ValueError):
                        existing_id = None
                    existing_categories: list[int] = []
                    for cid in existing.get("category_ids", []) if isinstance(existing, Mapping) else []:
                        try:
                            existing_categories.append(int(cid))
                        except (TypeError, ValueError):
                            continue
                    new_categories = list(existing_categories)
                    if xui_category_id is not None and xui_category_id not in new_categories:
                        new_categories.append(xui_category_id)
                    existing_icon = existing.get("stream_icon") if isinstance(existing, Mapping) else ""
                    existing_target = existing.get("target_container") if isinstance(existing, Mapping) else None
                    existing_properties = existing.get("movie_properties") if isinstance(existing, Mapping) else {}
                    existing_tag = existing.get("source_tag_filmes") if isinstance(existing, Mapping) else None
                    new_icon = icon or existing_icon or ""
                    new_target = target_container or existing_target
                    new_properties = properties or existing_properties or {}
                    current_tag = existing_tag
                    new_tag = source_tag or current_tag
                    differences: dict[str, Any] = {}
                    if new_categories != existing_categories:
                        differences["categoryIds"] = {
                            "from": existing_categories,
                            "to": new_categories,
                        }
                    if (new_icon or "") != (existing_icon or ""):
                        differences["icon"] = {
                            "from": existing_icon,
                            "to": new_icon,
                        }
                    if (new_target or "") != (existing_target or ""):
                        differences["targetContainer"] = {
                            "from": existing_target,
                            "to": new_target,
                        }
                    if new_properties != (existing_properties or {}):
                        differences["propertiesChanged"] = True
                    if (new_tag or "") != (current_tag or ""):
                        differences["sourceTag"] = {
                            "from": current_tag,
                            "to": new_tag,
                        }

                    bouquet_id_raw = adult_bouquet if is_adult else movies_bouquet
                    bouquet_id = _normalize_int(bouquet_id_raw)
                    if bouquet_id and existing_id is not None:
                        self._with_retry(self.repository.append_movie_to_bouquet, bouquet_id, existing_id)
                        self._apply_write_throttle()

                    status = "skipped"
                    if differences:
                        if existing_id is None:
                            raise RuntimeError("Registro de filme sem identificador")
                        self._with_retry(
                            self.repository.update_movie_metadata,
                            existing_id,
                            category_ids=new_categories,
                            icon=new_icon,
                            target_container=new_target,
                            properties=new_properties,
                            source_tag=new_tag,
                        )
                        self._apply_write_throttle()
                        updated_entry = {
                            "id": existing_id,
                            "category_ids": new_categories,
                            "stream_icon": new_icon,
                            "target_container": new_target,
                            "movie_properties": new_properties,
                            "source_tag_filmes": new_tag,
                        }
                        self._cache_movie(url, updated_entry)
                        self.updated += 1
                        status = "updated"
                        if new_tag and (new_tag or "") != (current_tag or ""):
                            self.domains[new_tag] += 1
                    else:
                        self.ignored += 1
                        self._cache_movie(
                            url,
                            {
                                "id": existing_id,
                                "category_ids": existing_categories,
                                "stream_icon": existing_icon,
                                "target_container": existing_target,
                                "movie_properties": existing_properties,
                                "source_tag_filmes": current_tag,
                            },
                        )

                    self.processed += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": status,
                            "title": title,
                            "url": url,
                            "streamId": existing_id,
                            "differences": differences,
                        }
                    )
                    self._commit()
                    continue

                stream_id_db = self._with_retry(
                    self.repository.insert_movie,
                    title=title,
                    category_id=xui_category_id,
                    urls=[url],
                    icon=icon,
                    target_container=target_container,
                    properties=properties,
                    source_tag=source_tag,
                )
                bouquet_id_raw = adult_bouquet if is_adult else movies_bouquet
                bouquet_id = _normalize_int(bouquet_id_raw)
                if bouquet_id:
                    self._with_retry(self.repository.append_movie_to_bouquet, bouquet_id, stream_id_db)
                    self._apply_write_throttle()

                self._apply_write_throttle()
                cached_entry = {
                    "id": stream_id_db,
                    "category_ids": [xui_category_id] if xui_category_id is not None else [],
                    "stream_icon": icon,
                    "target_container": target_container,
                    "movie_properties": properties,
                    "source_tag_filmes": source_tag,
                }
                self._cache_movie(url, cached_entry)

                self.inserted += 1
                self.processed += 1
                source_domain = dominio_de(url) or ""
                if source_tag:
                    self.domains[source_tag] += 1
                self._log(
                    {
                        "kind": "item",
                        "status": "inserted",
                        "title": title,
                        "url": url,
                        "categoryId": category_id,
                        "xuiCategoryId": xui_category_id,
                        "adult": is_adult,
                        "sourceTag": source_tag,
                        "sourceDomain": source_domain,
                        "streamId": stream_id_db,
                    }
                )
                self._commit()
            except Exception as exc:  # pragma: no cover - defensivo
                logger.exception("Falha ao importar filme %s: %s", entry.get("name"), exc)
                self.processed += 1
                self.errors += 1
                self._log(
                    {
                        "kind": "item",
                        "status": "error",
                        "title": entry.get("name") or entry.get("stream_id"),
                        "reason": str(exc),
                    }
                )
                self._commit()

        if self.domains:
            most_common = self.domains.most_common(1)[0][0]
            self.job.source_tag_filmes = most_common
            self.job.source_tag = most_common
            db.session.commit()


class _SeriesImporter(_BaseImporter):
    def execute(self) -> None:
        series_list = self.xtream.series()
        limit = _normalize_int(self.options.get("limitItems"))
        if limit and limit > 0:
            series_list = series_list[:limit]
        mapping = (self.options.get("categoryMapping", {}) or {}).get("series", {})
        bouquets = self.options.get("bouquets", {}) or {}
        series_bouquet = bouquets.get("series")
        adult_bouquet = bouquets.get("adult")
        tmdb_params = _build_tmdb_params(self.options)

        self.total_items = len(series_list)

        for entry in series_list:
            try:
                series_id = entry.get("series_id") or entry.get("id") or entry.get("stream_id")
                title = (entry.get("name") or entry.get("title") or "").strip()
                category_id = str(entry.get("category_id")) if entry.get("category_id") is not None else None
                category_name = entry.get("category_name")
                if not series_id or not title:
                    self.processed += 1
                    self.ignored += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "ignored",
                            "title": title or str(series_id),
                            "reason": "missing-data",
                        }
                    )
                    self._commit()
                    continue

                ignore_info = self._should_ignore("series", title, category_id, category_name)
                if ignore_info:
                    self.processed += 1
                    self.ignored += 1
                    log_payload = {
                        "kind": "item",
                        "status": "ignored",
                        "title": title,
                        "reason": f"ignored-{ignore_info['type']}",
                    }
                    if category_id:
                        log_payload["categoryId"] = category_id
                    if category_name:
                        log_payload["categoryName"] = category_name
                    if ignore_info["type"] == "prefix":
                        log_payload["prefix"] = ignore_info["value"]
                    self._log(log_payload)
                    self._commit()
                    continue

                xui_category = mapping.get(str(category_id)) if isinstance(mapping, dict) else None
                xui_category_id = _normalize_int(xui_category)
                if xui_category_id is None:
                    self.processed += 1
                    self.ignored += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "ignored",
                            "title": title,
                            "reason": "missing-category-mapping",
                            "categoryId": category_id,
                        }
                    )
                    self._commit()
                    continue

                try:
                    details = self.xtream.series_info(series_id)
                except XtreamError as exc:
                    self.processed += 1
                    self.errors += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "error",
                            "title": title,
                            "reason": str(exc),
                        }
                    )
                    self._commit()
                    continue

                episodes_payload = details.get("episodes") or {}
                if not isinstance(episodes_payload, dict):
                    episodes_payload = {}

                tmdb_payload = _fetch_tmdb_series(title, tmdb_params) if tmdb_params else {}
                poster = entry.get("cover") or entry.get("series_cover") or entry.get("cover_big")

                first_episode_url = None
                season_counter: Counter[str] = Counter()
                for season_key, episodes in episodes_payload.items():
                    if not isinstance(episodes, list):
                        continue
                    for ep in episodes:
                        info = ep.get("info") or {}
                        episode_id = ep.get("id")
                        if not episode_id:
                            continue
                        ext = (ep.get("container_extension") or "mp4").strip()
                        url = f"{self.xtream.base_url}/series/{self.xtream.username}/{self.xtream.password}/{episode_id}.{ext}"
                        first_episode_url = first_episode_url or url
                        tag = source_tag_from_url(url)
                        if tag:
                            season_counter[tag] += 1
                if not first_episode_url:
                    self.processed += 1
                    self.ignored += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "ignored",
                            "title": title,
                            "reason": "no-episodes",
                        }
                    )
                    self._commit()
                    continue

                primary_tag = season_counter.most_common(1)[0][0] if season_counter else None

                existing = self._with_retry(self.repository.fetch_series, title, primary_tag)
                if existing:
                    series_id_db = int(existing["id"])
                else:
                    series_id_db = self._with_retry(
                        self.repository.create_series,
                        title=title,
                        category_id=xui_category_id,
                        cover=poster,
                        backdrop=tmdb_payload.get("backdrop"),
                        plot=tmdb_payload.get("overview"),
                        rating=tmdb_payload.get("rating"),
                        tmdb_language=tmdb_language,
                        source_tag=primary_tag,
                    )
                    self._apply_write_throttle()

                is_adult_series = _is_adult(title, category_name, category_id, self.options)
                bouquet_id_raw = adult_bouquet if is_adult_series else series_bouquet
                bouquet_id = _normalize_int(bouquet_id_raw)
                if bouquet_id:
                    self._with_retry(self.repository.append_series_to_bouquet, bouquet_id, series_id_db)
                    self._apply_write_throttle()

                inserted_episodes = 0
                updated_episodes = 0
                skipped_episodes = 0
                for season_key, episodes in episodes_payload.items():
                    if not isinstance(episodes, list):
                        continue
                    for ep in episodes:
                        episode_id = ep.get("id")
                        if not episode_id:
                            continue
                        info = ep.get("info") or {}
                        ext = (ep.get("container_extension") or "mp4").strip()
                        season_number = int(info.get("season") or season_key or 0)
                        episode_number = int(info.get("episode_num") or ep.get("episode_num") or 0)
                        title_ep = ep.get("title") or f"{title} S{season_number:02d}E{episode_number:02d}"
                        url = f"{self.xtream.base_url}/series/{self.xtream.username}/{self.xtream.password}/{episode_id}.{ext}"
                        props = _episode_properties(tmdb_payload, poster, season_number)
                        stream_tag = source_tag_from_url(url)
                        target_container = target_container_from_url(url)
                        existing_episode = self._get_cached_episode(url)
                        if existing_episode:
                            episode_id_raw = existing_episode.get("id") if isinstance(existing_episode, Mapping) else None
                            try:
                                existing_episode_id = int(episode_id_raw) if episode_id_raw is not None else None
                            except (TypeError, ValueError):
                                existing_episode_id = None
                            existing_categories: list[int] = []
                            category_iterable = (
                                existing_episode.get("category_ids", [])
                                if isinstance(existing_episode, Mapping)
                                else []
                            )
                            for cid in category_iterable:
                                try:
                                    existing_categories.append(int(cid))
                                except (TypeError, ValueError):
                                    continue
                            new_categories = list(existing_categories)
                            if xui_category_id is not None and xui_category_id not in new_categories:
                                new_categories.append(xui_category_id)
                            existing_icon = (
                                existing_episode.get("stream_icon") if isinstance(existing_episode, Mapping) else ""
                            )
                            existing_target = (
                                existing_episode.get("target_container")
                                if isinstance(existing_episode, Mapping)
                                else None
                            )
                            existing_properties = (
                                existing_episode.get("movie_properties")
                                if isinstance(existing_episode, Mapping)
                                else {}
                            )
                            existing_tag = (
                                existing_episode.get("source_tag") if isinstance(existing_episode, Mapping) else None
                            )
                            new_icon = poster or existing_icon or ""
                            new_target = target_container or existing_target
                            new_properties = props or existing_properties or {}
                            current_tag = existing_tag
                            new_tag = stream_tag or current_tag
                            differences: dict[str, Any] = {}
                            if new_categories != existing_categories:
                                differences["categoryIds"] = {
                                    "from": existing_categories,
                                    "to": new_categories,
                                }
                            if (new_icon or "") != (existing_icon or ""):
                                differences["icon"] = {
                                    "from": existing_icon,
                                    "to": new_icon,
                                }
                            if (new_target or "") != (existing_target or ""):
                                differences["targetContainer"] = {
                                    "from": existing_target,
                                    "to": new_target,
                                }
                            if new_properties != (existing_properties or {}):
                                differences["propertiesChanged"] = True
                            if (new_tag or "") != (current_tag or ""):
                                differences["sourceTag"] = {
                                    "from": current_tag,
                                    "to": new_tag,
                                }

                            if differences:
                                if existing_episode_id is None:
                                    raise RuntimeError("Episódio sem identificador")
                                self._with_retry(
                                    self.repository.update_episode_metadata,
                                    existing_episode_id,
                                    category_ids=new_categories,
                                    icon=new_icon,
                                    target_container=new_target,
                                    properties=new_properties,
                                    source_tag=new_tag,
                                )
                                self._apply_write_throttle()
                                updated_entry = {
                                    "id": existing_episode_id,
                                    "category_ids": new_categories,
                                    "stream_icon": new_icon,
                                    "target_container": new_target,
                                    "movie_properties": new_properties,
                                    "source_tag": new_tag,
                                }
                                self._cache_episode(url, updated_entry)
                                updated_episodes += 1
                                self.updated += 1
                                if new_tag and (new_tag or "") != (current_tag or ""):
                                    self.domains[new_tag] += 1
                            else:
                                skipped_episodes += 1
                                self.ignored += 1
                                self._cache_episode(
                                    url,
                                    {
                                        "id": existing_episode_id,
                                        "category_ids": existing_categories,
                                        "stream_icon": existing_icon,
                                        "target_container": existing_target,
                                        "movie_properties": existing_properties,
                                        "source_tag": current_tag,
                                    },
                                )
                            continue

                        stream_id_episode = self._with_retry(
                            self.repository.insert_episode,
                            stream_title=title_ep,
                            urls=[url],
                            icon=poster,
                            target_container=target_container,
                            properties=props,
                            series_id=series_id_db,
                            season=season_number,
                            episode=episode_number,
                            source_tag=stream_tag,
                        )
                        self._apply_write_throttle()
                        self._cache_episode(
                            url,
                            {
                                "id": stream_id_episode,
                                "category_ids": [],
                                "stream_icon": poster,
                                "target_container": target_container,
                                "movie_properties": props,
                                "source_tag": stream_tag,
                            },
                        )
                        if stream_tag:
                            self.domains[stream_tag] += 1
                        inserted_episodes += 1

                self.inserted += inserted_episodes
                self.processed += 1
                if inserted_episodes == 0 and updated_episodes == 0:
                    self.ignored += 1
                self._log(
                    {
                        "kind": "item",
                        "status": "processed",
                        "title": title,
                        "episodesInserted": inserted_episodes,
                        "episodesUpdated": updated_episodes,
                        "episodesSkipped": skipped_episodes,
                        "seriesId": series_id_db,
                        "sourceTag": primary_tag,
                    }
                )
                self._commit()
            except Exception as exc:  # pragma: no cover - defensivo
                logger.exception("Falha ao importar série %s: %s", entry.get("name"), exc)
                self.processed += 1
                self.errors += 1
                self._log(
                    {
                        "kind": "item",
                        "status": "error",
                        "title": entry.get("name") or entry.get("series_id"),
                        "reason": str(exc),
                    }
                )
                self._commit()

        if self.domains:
            most_common = self.domains.most_common(1)[0][0]
            self.job.source_tag = most_common
            db.session.commit()


@celery_app.task(name="tasks.run_import")
def run_import(tipo: str, tenant_id: str, user_id: int, job_id: int | None = None):
    if tipo not in _IMPORT_TYPES:
        logger.error("Tipo de importação inválido: %s", tipo)
        return

    job = _ensure_job(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job_id)

    try:
        worker_config = get_worker_config(tenant_id)
        if not worker_config.get("xui_db_uri"):
            raise RuntimeError("xui_db_uri não configurado")
        if not worker_config.get("xtream_base_url"):
            raise RuntimeError("xtream_base_url não configurado")
        if not worker_config.get("xtream_username") or not worker_config.get("xtream_password"):
            raise RuntimeError("Credenciais da API Xtream não configuradas")

        xtream_options = worker_config.get("options", {}) or {}
        throttle_ms = int(xtream_options.get("throttleMs") or 0)
        retry_opts = xtream_options.get("retry", {}) or {}
        max_parallel = int(xtream_options.get("maxParallel") or 1)
        xtream_client = XtreamClient(
            base_url=worker_config["xtream_base_url"],
            username=worker_config["xtream_username"],
            password=worker_config["xtream_password"],
            timeout=30,
            throttle_ms=throttle_ms,
            max_retries=int(retry_opts.get("maxAttempts") or 3),
            backoff_seconds=int(retry_opts.get("backoffSeconds") or 5),
            max_parallel=max_parallel,
        )

        engine = get_engine(tenant_id, XuiCredentials(worker_config["xui_db_uri"]))
        repository = XuiRepository(engine)
        repository.ensure_compatibility()

        normalization_result = repository.normalize_sources()
        _log_normalization(job, normalization_result)
        if tipo == "filmes":
            importer = _MovieImporter(
                job=job,
                tenant_id=tenant_id,
                repository=repository,
                xtream=xtream_client,
                options=xtream_options,
            )
        else:
            importer = _SeriesImporter(
                job=job,
                tenant_id=tenant_id,
                repository=repository,
                xtream=xtream_client,
                options=xtream_options,
            )

        importer.execute()
        importer.finalize()

        job.status = JobStatus.FINISHED
        job.progress = 1.0
        job.finished_at = datetime.utcnow()
        job.duration_sec = int((job.finished_at - job.started_at).total_seconds()) if job.started_at else None
        job.inserted = importer.inserted
        job.updated = importer.updated
        job.ignored = importer.ignored
        job.errors = importer.errors
        job.eta_sec = None

        summary = {
            "kind": "summary",
            "totals": {
                "inserted": importer.inserted,
                "updated": importer.updated,
                "ignored": importer.ignored,
                "errors": importer.errors,
            },
            "durationSec": job.duration_sec,
        }
        db.session.add(JobLog(job_id=job.id, content=json.dumps(summary, ensure_ascii=False)))
        db.session.commit()

    except (XtreamError, RuntimeError, SQLAlchemyError, requests.RequestException) as exc:
        logger.exception("Importação %s falhou: %s", tipo, exc)
        db.session.rollback()
        job = Job.query.get(job.id)
        if job:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.utcnow()
            job.duration_sec = int((job.finished_at - job.started_at).total_seconds()) if job.started_at else None
            job.error = str(exc)
            job.eta_sec = None
            db.session.add(
                JobLog(
                    job_id=job.id,
                    content=json.dumps({"kind": "error", "message": str(exc)}, ensure_ascii=False),
                )
            )
            db.session.commit()
        raise

    except Exception as exc:  # pragma: no cover - fallback para erros inesperados
        logger.exception("Erro inesperado durante importação %s: %s", tipo, exc)
        db.session.rollback()
        job = Job.query.get(job.id)
        if job:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.utcnow()
            job.duration_sec = int((job.finished_at - job.started_at).total_seconds()) if job.started_at else None
            job.error = str(exc)
            job.eta_sec = None
            db.session.add(
                JobLog(
                    job_id=job.id,
                    content=json.dumps({"kind": "error", "message": str(exc)}, ensure_ascii=False),
                )
            )
            db.session.commit()
        raise
