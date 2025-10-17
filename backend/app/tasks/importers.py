"""Importadores Celery portados dos scripts legados."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.exc import SQLAlchemyError

from ..config import Config
from ..extensions import celery_app, db
from ..models import (
    Bouquet,
    BouquetItem,
    Job,
    JobLog,
    JobStatus,
    Stream,
    StreamEpisode,
    StreamSeries,
)
from ..services import tmdb, bouquets as bouquet_service
from ..services.importers import (
    categoria_adulta,
    dominio_de,
    limpar_nome,
    normalize_stream_source,
    source_tag_from_url,
    target_container_from_url,
)
from ..services.legacy_sources import MovieCandidate, SeriesEpisodeCandidate, iter_movies_from_m3u, iter_series_from_m3u

logger = logging.getLogger(__name__)

_IMPORT_TYPES = {"filmes", "series"}
_PROGRESS_CHUNK = 10
_MOVIE_TYPE = 2
_EPISODE_TYPE = 5
_DEFAULT_BOUQUETS = {
    "movies": "Filmes",
    "series": "Séries",
    "adult": "Adultos",
}

_config = Config()


def _ensure_job(tipo: str, tenant_id: str, user_id: int, job_id: int | None) -> Job:
    job: Job | None = None
    if job_id:
        job = Job.query.filter_by(id=job_id, tenant_id=tenant_id, user_id=user_id).first()
    if not job:
        job = Job(
            tenant_id=tenant_id,
            user_id=user_id,
            type=tipo,
        )
        db.session.add(job)
        db.session.commit()
    job.type = tipo
    job.status = JobStatus.RUNNING
    job.progress = 0.0
    job.eta_sec = None
    job.started_at = datetime.utcnow()
    job.finished_at = None
    job.error = None
    job.inserted = 0
    job.updated = 0
    job.ignored = 0
    job.errors = 0
    job.duration_sec = None
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
    avg = elapsed / max(processed, 1)
    return int(max(avg * remaining, 0))


def _persist_logs(job: Job, entries: list[dict]) -> None:
    if not entries:
        return
    db.session.add_all(
        [JobLog(job_id=job.id, content=json.dumps(entry, ensure_ascii=False)) for entry in entries]
    )
    db.session.flush()


def _ensure_bouquets(tenant_id: str) -> dict[str, Bouquet]:
    mapping: dict[str, Bouquet] = {}
    for key, name in _DEFAULT_BOUQUETS.items():
        bouquet = Bouquet.query.filter_by(tenant_id=tenant_id, name=name).first()
        if not bouquet:
            bouquet = Bouquet(tenant_id=tenant_id, name=name)
            db.session.add(bouquet)
            db.session.flush()
        mapping[key] = bouquet
    return mapping


def _upsert_bouquet_item(
    bouquet: Bouquet,
    content_id: str,
    item_type: str,
    title: str,
    metadata: dict,
    source_tag: Optional[str] = None,
    source_tag_filmes: Optional[str] = None,
) -> None:
    existing = BouquetItem.query.filter_by(bouquet_id=bouquet.id, content_id=content_id).first()
    if existing:
        existing.title = title
        existing.type = item_type
        existing.metadata_json = metadata
        existing.source_tag = source_tag
        existing.source_tag_filmes = source_tag_filmes
        return

    db.session.add(
        BouquetItem(
            bouquet_id=bouquet.id,
            content_id=content_id,
            type=item_type,
            title=title,
            metadata_json=metadata,
            source_tag=source_tag,
            source_tag_filmes=source_tag_filmes,
        )
    )


def _movie_metadata_from_tmdb(candidate: MovieCandidate) -> tuple[Optional[int], dict]:
    try:
        details: dict | None = None
        tmdb_id = candidate.tmdb_id
        query = limpar_nome(candidate.title)
        if tmdb_id:
            details = tmdb.fetch_movie_details(tmdb_id)
        else:
            search = tmdb.search_movies(query)
            results = search.get("results") or []
            if results:
                tmdb_id = results[0].get("id")
                if tmdb_id:
                    details = tmdb.fetch_movie_details(tmdb_id)
        if not details:
            return None, {}
        metadata: dict = {}
        metadata["year"] = (details.get("release_date") or "").split("-", 1)[0] or None
        genres = details.get("genres") or []
        metadata["genres"] = [genre.get("name") for genre in genres if genre.get("name")]
        metadata["poster"] = details.get("poster_path")
        metadata["backdrop"] = details.get("backdrop_path")
        metadata["overview"] = details.get("overview")
        metadata["rating"] = details.get("vote_average")
        metadata["runtime"] = details.get("runtime")
        return tmdb_id, metadata
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("TMDb indisponível para %s: %s", candidate.title, exc)
        return None, {}


def _series_metadata_from_tmdb(series_title: str, tmdb_id: Optional[int]) -> tuple[Optional[int], dict]:
    try:
        details: dict | None = None
        query = limpar_nome(series_title)
        identifier = tmdb_id
        if identifier:
            details = tmdb.fetch_series_details(identifier)
        else:
            search = tmdb.search_series(query)
            results = search.get("results") or []
            if results:
                identifier = results[0].get("id")
                if identifier:
                    details = tmdb.fetch_series_details(identifier)
        if not details:
            return None, {}
        metadata: dict = {}
        metadata["genres"] = [genre.get("name") for genre in details.get("genres", []) if genre.get("name")]
        metadata["poster"] = details.get("poster_path")
        metadata["backdrop"] = details.get("backdrop_path")
        metadata["overview"] = details.get("overview")
        metadata["rating"] = details.get("vote_average")
        metadata["seasons"] = details.get("number_of_seasons")
        return identifier, metadata
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("TMDb indisponível para série %s: %s", series_title, exc)
        return None, {}


class _BaseImporter:
    def __init__(self, job: Job, tenant_id: str) -> None:
        self.job = job
        self.tenant_id = tenant_id
        self.start_time = datetime.utcnow()
        self.logs_buffer: list[dict] = []
        self.total_items = 0
        self.processed = 0
        self.inserted = 0
        self.updated = 0
        self.ignored = 0
        self.errors = 0

    def _persist_if_needed(self) -> None:
        self.job.progress = (self.processed / self.total_items) if self.total_items else 1.0
        self.job.inserted = self.inserted
        self.job.updated = self.updated
        self.job.ignored = self.ignored
        self.job.errors = self.errors
        self.job.eta_sec = _estimate_eta(self.start_time, self.processed, self.total_items)
        if len(self.logs_buffer) >= _PROGRESS_CHUNK:
            _persist_logs(self.job, self.logs_buffer)
            self.logs_buffer.clear()
        db.session.commit()

    def _append_log(self, payload: dict) -> None:
        self.logs_buffer.append(payload)

    def finalize(self) -> None:
        if self.logs_buffer:
            _persist_logs(self.job, self.logs_buffer)
            self.logs_buffer.clear()
        db.session.commit()

    def execute(self) -> None:
        raise NotImplementedError


class _MovieImporter(_BaseImporter):
    def execute(self) -> None:
        candidates = list(iter_movies_from_m3u(_config.LEGACY_MOVIES_M3U))
        self.total_items = len(candidates)
        bouquets = _ensure_bouquets(self.tenant_id)
        domains: list[str] = []

        for candidate in candidates:
            urls = normalize_stream_source(candidate.urls)
            if not urls:
                self.processed += 1
                self.ignored += 1
                self._append_log(
                    {
                        "kind": "item",
                        "status": "ignored",
                        "title": candidate.title,
                        "origin": candidate.origin,
                        "reason": "empty-url",
                    }
                )
                self._persist_if_needed()
                continue

            primary_url = urls[0]
            source_tag = source_tag_from_url(primary_url)
            source_domain = dominio_de(primary_url)
            is_adult = categoria_adulta(candidate.title) or categoria_adulta(candidate.category)
            existing = Stream.query.filter_by(tenant_id=self.tenant_id, primary_url=primary_url).first()
            if existing:
                self.processed += 1
                self.ignored += 1
                self._append_log(
                    {
                        "kind": "item",
                        "status": "duplicate",
                        "title": candidate.title,
                        "category": candidate.category,
                        "origin": candidate.origin,
                        "url": primary_url,
                        "adult": existing.is_adult or is_adult,
                        "source_domain": source_domain,
                        "source_tag_filmes": existing.source_tag_filmes,
                    }
                )
                self._persist_if_needed()
                continue

            tmdb_id, metadata = _movie_metadata_from_tmdb(candidate)
            metadata.setdefault("genres", [])
            metadata.setdefault("year", None)
            metadata.setdefault("poster", None)
            metadata.setdefault("overview", None)
            metadata.setdefault("runtime", None)
            metadata["source_domain"] = source_domain

            stream = Stream(
                tenant_id=self.tenant_id,
                type=_MOVIE_TYPE,
                title=candidate.title,
                category=candidate.category,
                group_title=candidate.category,
                is_adult=is_adult,
                stream_source=urls,
                primary_url=primary_url,
                target_container=target_container_from_url(primary_url),
                source_tag_filmes=source_tag,
                source_tag=source_tag,
                tmdb_id=tmdb_id,
                movie_properties=metadata,
            )
            db.session.add(stream)
            db.session.flush()

            content_id = f"f_{stream.id}"
            bouquet_metadata = {
                "year": metadata.get("year"),
                "genres": metadata.get("genres", []),
                "poster": metadata.get("poster"),
                "overview": metadata.get("overview"),
                "runtime": metadata.get("runtime"),
                "adult": is_adult,
                "source_domain": source_domain,
            }
            _upsert_bouquet_item(
                bouquets["adult" if is_adult else "movies"],
                content_id,
                "movie",
                candidate.title,
                bouquet_metadata,
                source_tag=source_tag,
                source_tag_filmes=source_tag,
            )
            if is_adult:
                _upsert_bouquet_item(
                    bouquets["movies"],
                    content_id,
                    "movie",
                    candidate.title,
                    bouquet_metadata,
                    source_tag=source_tag,
                    source_tag_filmes=source_tag,
                )

            self.inserted += 1
            self.processed += 1
            domains.append(source_tag or "")
            self._append_log(
                {
                    "kind": "item",
                    "status": "inserted",
                    "title": candidate.title,
                    "category": candidate.category,
                    "origin": candidate.origin,
                    "url": primary_url,
                    "adult": is_adult,
                    "source_tag_filmes": source_tag,
                    "source_domain": source_domain,
                    "tmdb_id": tmdb_id,
                }
            )
            self._persist_if_needed()

        # Definir tag do job pelas origens mais frequentes
        if domains:
            domain_counter = Counter(filter(None, domains))
            if domain_counter:
                tag = domain_counter.most_common(1)[0][0]
                self.job.source_tag_filmes = tag
                self.job.source_tag = tag
                db.session.commit()

        bouquet_service.invalidate_catalog_cache(self.tenant_id)


class _SeriesImporter(_BaseImporter):
    def execute(self) -> None:
        candidates = list(iter_series_from_m3u(_config.LEGACY_SERIES_M3U))
        self.total_items = len(candidates)
        bouquets = _ensure_bouquets(self.tenant_id)
        series_cache: dict[tuple[str, Optional[str]], StreamSeries] = {}

        episodes_by_series: dict[tuple[str, Optional[str]], list[SeriesEpisodeCandidate]] = defaultdict(list)
        job_domains: list[str] = []
        for candidate in candidates:
            urls = normalize_stream_source(candidate.urls)
            if not urls:
                self.processed += 1
                self.ignored += 1
                self._append_log(
                    {
                        "kind": "item",
                        "status": "ignored",
                        "title": candidate.title,
                        "origin": candidate.origin,
                        "reason": "empty-url",
                    }
                )
                self._persist_if_needed()
                continue
            tag = source_tag_from_url(urls[0])
            key = (limpar_nome(candidate.title_base) or candidate.title_base, tag)
            episodes_by_series[key].append(candidate)

        for key, episodes in episodes_by_series.items():
            title_base, source_tag = key
            first_episode = episodes[0]
            normalized_title = limpar_nome(first_episode.title_base) or first_episode.title_base
            existing_series = StreamSeries.query.filter_by(
                tenant_id=self.tenant_id,
                title_base=title_base,
                source_tag=source_tag,
            ).first()
            if not existing_series and source_tag:
                existing_series = StreamSeries.query.filter_by(
                    tenant_id=self.tenant_id,
                    title_base=title_base,
                    source_tag=None,
                ).first()
                if existing_series:
                    existing_series.source_tag = source_tag
            if not existing_series:
                tmdb_id, metadata = _series_metadata_from_tmdb(normalized_title, first_episode.tmdb_id)
                series_is_adult = categoria_adulta(first_episode.title) or categoria_adulta(first_episode.category)
                existing_series = StreamSeries(
                    tenant_id=self.tenant_id,
                    title=normalized_title,
                    title_base=title_base,
                    source_tag=source_tag,
                    tmdb_id=tmdb_id,
                    overview=metadata.get("overview"),
                    poster=metadata.get("poster"),
                    backdrop=metadata.get("backdrop"),
                    rating=metadata.get("rating"),
                    genres=metadata.get("genres"),
                    seasons=metadata.get("seasons"),
                    is_adult=series_is_adult,
                )
                db.session.add(existing_series)
                db.session.flush()
            series_cache[key] = existing_series

            seasons_seen: set[int] = set()
            domain_counter: Counter[str] = Counter()

            for episode in episodes:
                urls = normalize_stream_source(episode.urls)
                primary_url = urls[0]
                stream_tag = source_tag_from_url(primary_url) or "unknown"
                domain_counter[stream_tag] += 1
                seasons_seen.add(episode.season)
                is_adult = categoria_adulta(episode.title) or categoria_adulta(episode.category)
                existing_stream = Stream.query.filter_by(
                    tenant_id=self.tenant_id,
                    primary_url=primary_url,
                ).first()
                if existing_stream:
                    self.processed += 1
                    self.ignored += 1
                    self._append_log(
                        {
                            "kind": "item",
                            "status": "duplicate",
                            "title": episode.title,
                            "series": normalized_title,
                            "origin": episode.origin,
                            "url": primary_url,
                            "adult": existing_stream.is_adult or is_adult,
                            "source_tag": existing_stream.source_tag,
                        }
                    )
                    self._persist_if_needed()
                    continue

                stream = Stream(
                    tenant_id=self.tenant_id,
                    type=_EPISODE_TYPE,
                    title=episode.title,
                    category=episode.category,
                    group_title=episode.category,
                    is_adult=is_adult,
                    stream_source=urls,
                    primary_url=primary_url,
                    target_container=target_container_from_url(primary_url),
                    source_tag=None if stream_tag == "unknown" else stream_tag,
                )
                db.session.add(stream)
                db.session.flush()

                db.session.add(
                    StreamEpisode(
                        tenant_id=self.tenant_id,
                        stream_id=stream.id,
                        series_id=existing_series.id,
                        season=episode.season,
                        episode=episode.episode,
                        title=episode.title,
                    )
                )

                self.inserted += 1
                self.processed += 1
                self._append_log(
                    {
                        "kind": "item",
                        "status": "inserted",
                        "title": episode.title,
                        "series": normalized_title,
                        "season": episode.season,
                        "episode": episode.episode,
                        "origin": episode.origin,
                        "url": primary_url,
                        "adult": is_adult,
                        "source_tag": stream.source_tag,
                    }
                )
                self._persist_if_needed()

            if existing_series:
                if domain_counter:
                    common_tag, _count = domain_counter.most_common(1)[0]
                    existing_series.source_tag = common_tag if common_tag != "unknown" else existing_series.source_tag
                    if common_tag != "unknown":
                        job_domains.append(common_tag)
                existing_series.is_adult = existing_series.is_adult or categoria_adulta(first_episode.title) or categoria_adulta(first_episode.category)
                existing_series.seasons = max(existing_series.seasons or 0, len(seasons_seen))
                db.session.commit()

                metadata = {
                    "genres": existing_series.genres or [],
                    "poster": existing_series.poster,
                    "overview": existing_series.overview,
                    "seasons": existing_series.seasons,
                    "adult": existing_series.is_adult,
                }
                _upsert_bouquet_item(
                    bouquets["adult" if existing_series.is_adult else "series"],
                    f"s_{existing_series.id}",
                    "series",
                    existing_series.title,
                    metadata,
                    source_tag=existing_series.source_tag,
                )
                if existing_series.is_adult:
                    _upsert_bouquet_item(
                        bouquets["series"],
                        f"s_{existing_series.id}",
                        "series",
                        existing_series.title,
                        metadata,
                        source_tag=existing_series.source_tag,
                    )

        if job_domains:
            domain_counter = Counter(filter(None, job_domains))
            if domain_counter:
                self.job.source_tag = domain_counter.most_common(1)[0][0]
                db.session.commit()

        bouquet_service.invalidate_catalog_cache(self.tenant_id)


@celery_app.task(name="tasks.run_import")
def run_import(tipo: str, tenant_id: str, user_id: int, job_id: int | None = None):
    if tipo not in _IMPORT_TYPES:
        logger.error("Tipo de importação inválido: %s", tipo)
        return

    job = _ensure_job(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job_id)
    importer_cls: Callable[[Job, str], _BaseImporter]
    if tipo == "filmes":
        importer_cls = _MovieImporter
    else:
        importer_cls = _SeriesImporter

    importer = importer_cls(job, tenant_id)

    try:
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

    except Exception as exc:  # pragma: no cover - defensivo
        logger.exception("Importação %s falhou: %s", tipo, exc)
        db.session.rollback()
        try:
            job = Job.query.get(job.id)
            if job:
                job.status = JobStatus.FAILED
                job.finished_at = datetime.utcnow()
                job.duration_sec = (
                    int((job.finished_at - job.started_at).total_seconds()) if job.started_at else None
                )
                job.errors = importer.errors + 1
                job.error = str(exc)
                job.eta_sec = None
                db.session.add(
                    JobLog(
                        job_id=job.id,
                        content=json.dumps(
                            {
                                "kind": "error",
                                "message": str(exc),
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                db.session.commit()
        except SQLAlchemyError:
            logger.exception("Falha ao atualizar job após erro")
        raise
