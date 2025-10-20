"""Importadores Celery que sincronizam o catálogo diretamente no XUI."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Iterable, Mapping

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
    api_key = tmdb_opts.get("apiKey") or _CONFIG.TMDB_API_KEY
    if not enabled or not api_key:
        return None
    return {
        "api_key": api_key,
        "language": tmdb_opts.get("language") or _CONFIG.TMDB_LANGUAGE,
        "region": tmdb_opts.get("region") or _CONFIG.TMDB_REGION,
    }


def _fetch_tmdb_movie(title: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"query": title, **params, "page": 1, "include_adult": True},
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
        response = requests.get(
            "https://api.themoviedb.org/3/search/tv",
            params={"query": title, **params, "page": 1},
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
        self.ignored = 0
        self.errors = 0
        self.domains: Counter[str] = Counter()

    def _log(self, payload: Mapping[str, Any]) -> None:
        self.buffer.append(dict(payload))
        if len(self.buffer) >= _LOG_BATCH:
            _persist_logs(self.job, self.buffer)
            self.buffer.clear()

    def _commit(self) -> None:
        self.job.progress = (self.processed / self.total_items) if self.total_items else 1.0
        self.job.inserted = self.inserted
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


class _MovieImporter(_BaseImporter):
    def execute(self) -> None:
        data = self.xtream.vod_streams()
        limit = _normalize_int(self.options.get("limitItems"))
        if limit and limit > 0:
            data = data[:limit]
        mapping = (self.options.get("categoryMapping", {}) or {}).get("movies", {})
        tmdb_params = _build_tmdb_params(self.options)
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
                duplicate = self.repository.movie_url_exists(url)
                if duplicate:
                    self.processed += 1
                    self.ignored += 1
                    self._log(
                        {
                            "kind": "item",
                            "status": "duplicate",
                            "title": title,
                            "url": url,
                            "existingSourceTag": duplicate.get("source_tag_filmes"),
                        }
                    )
                    self._commit()
                    continue

                tmdb_payload = _fetch_tmdb_movie(title, tmdb_params) if tmdb_params else {}
                properties = _movie_properties(title, tmdb_payload, icon)
                is_adult = _is_adult(title, category_name, category_id, self.options)
                target_container = target_container_from_url(url)
                source_tag = source_tag_from_url(url)
                stream_id_db = self.repository.insert_movie(
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
                    self.repository.append_movie_to_bouquet(bouquet_id, stream_id_db)

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

                existing = self.repository.fetch_series(title, primary_tag)
                if existing:
                    series_id_db = int(existing["id"])
                else:
                    series_id_db = self.repository.create_series(
                        title=title,
                        category_id=xui_category_id,
                        cover=poster,
                        backdrop=tmdb_payload.get("backdrop"),
                        plot=tmdb_payload.get("overview"),
                        rating=tmdb_payload.get("rating"),
                        tmdb_language=(self.options.get("tmdb", {}) or {}).get("language", "pt-BR"),
                        source_tag=primary_tag,
                    )

                is_adult_series = _is_adult(title, entry.get("category_name"), category_id, self.options)
                bouquet_id_raw = adult_bouquet if is_adult_series else series_bouquet
                bouquet_id = _normalize_int(bouquet_id_raw)
                if bouquet_id:
                    self.repository.append_series_to_bouquet(bouquet_id, series_id_db)

                inserted_episodes = 0
                duplicate_episodes = 0
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
                        if self.repository.episode_url_exists(url):
                            duplicate_episodes += 1
                            continue
                        props = _episode_properties(tmdb_payload, poster, season_number)
                        stream_tag = source_tag_from_url(url)
                        target_container = target_container_from_url(url)
                        self.repository.insert_episode(
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
                        if stream_tag:
                            self.domains[stream_tag] += 1
                        inserted_episodes += 1

                self.inserted += inserted_episodes
                self.processed += 1
                if inserted_episodes == 0:
                    self.ignored += 1
                if duplicate_episodes:
                    self.ignored += duplicate_episodes
                self._log(
                    {
                        "kind": "item",
                        "status": "processed",
                        "title": title,
                        "episodesInserted": inserted_episodes,
                        "episodesDuplicate": duplicate_episodes,
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


def _build_importer(tipo: str, job: Job, tenant_id: str) -> tuple[_BaseImporter, XtreamClient]:
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
    xtream_client = XtreamClient(
        base_url=worker_config["xtream_base_url"],
        username=worker_config["xtream_username"],
        password=worker_config["xtream_password"],
        timeout=30,
        throttle_ms=throttle_ms,
        max_retries=int(retry_opts.get("maxAttempts") or 3),
        backoff_seconds=int(retry_opts.get("backoffSeconds") or 5),
    )

    engine = get_engine(tenant_id, XuiCredentials(worker_config["xui_db_uri"]))
    repository = XuiRepository(engine)
    repository.ensure_compatibility()

    if tipo == "filmes":
        importer = _MovieImporter(job=job, tenant_id=tenant_id, repository=repository, xtream=xtream_client, options=xtream_options)
    else:
        importer = _SeriesImporter(job=job, tenant_id=tenant_id, repository=repository, xtream=xtream_client, options=xtream_options)
    return importer, xtream_client


@celery_app.task(name="tasks.run_import")
def run_import(tipo: str, tenant_id: str, user_id: int, job_id: int | None = None):
    if tipo not in _IMPORT_TYPES:
        logger.error("Tipo de importação inválido: %s", tipo)
        return

    job = _ensure_job(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job_id)

    try:
        importer, _ = _build_importer(tipo, job, tenant_id)
        normalization_result = importer.repository.normalize_stream_sources()
        _log_normalization(job, normalization_result)
        importer.execute()
        importer.finalize()

        job.status = JobStatus.FINISHED
        job.progress = 1.0
        job.finished_at = datetime.utcnow()
        job.duration_sec = int((job.finished_at - job.started_at).total_seconds()) if job.started_at else None
        job.inserted = importer.inserted
        job.ignored = importer.ignored
        job.errors = importer.errors
        job.updated = 0
        job.eta_sec = None

        summary = {
            "kind": "summary",
            "totals": {
                "inserted": importer.inserted,
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
