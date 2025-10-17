"""Importadores Celery integrados ao TMDb."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import celery_app, db
from ..models import Job, JobLog, JobStatus
from ..services import tmdb

logger = logging.getLogger(__name__)

_IMPORT_TYPES = {"filmes", "series"}
_ITEMS_TO_FETCH = 50
_PROGRESS_CHUNK = 10


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
    db.session.commit()
    return job


def _discover(tipo: str, page: int) -> dict:
    if tipo == "filmes":
        return tmdb.discover_movies(page=page)
    return tmdb.discover_series(page=page)


def _fetch_details(tipo: str, tmdb_id: int) -> dict:
    if tipo == "filmes":
        return tmdb.fetch_movie_details(tmdb_id)
    return tmdb.fetch_series_details(tmdb_id)


def _extract_year(payload: dict) -> int | None:
    date_field = payload.get("release_date") or payload.get("first_air_date")
    if not date_field:
        return None
    try:
        return int(date_field.split("-", 1)[0])
    except (ValueError, AttributeError):
        return None


def _genre_names(tipo: str, payload: dict) -> list[str]:
    genre_key = "genres" if "genres" in payload else "genre_ids"
    raw_genres = payload.get(genre_key) or []
    if raw_genres and isinstance(raw_genres[0], dict):
        return [genre.get("name") for genre in raw_genres if genre.get("name")]
    if tipo == "filmes":
        mapping = tmdb.movie_genres()
    else:
        mapping = tmdb.series_genres()
    return [mapping.get(genre_id) for genre_id in raw_genres if mapping.get(genre_id)]


def _estimate_eta(start_time: datetime, processed: int) -> int | None:
    if processed <= 0:
        return None
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    avg = elapsed / processed
    remaining = max(_ITEMS_TO_FETCH - processed, 0)
    return int(math.ceil(avg * remaining)) if remaining else None


def _persist_logs(job: Job, entries: list[dict]) -> None:
    if not entries:
        return
    db.session.add_all(
        [JobLog(job_id=job.id, content=json.dumps(entry, ensure_ascii=False)) for entry in entries]
    )
    db.session.commit()


@celery_app.task(name="tasks.run_import")
def run_import(tipo: str, tenant_id: str, user_id: int, job_id: int | None = None):
    if tipo not in _IMPORT_TYPES:
        logger.error("Tipo de importação inválido: %s", tipo)
        return

    job = _ensure_job(tipo=tipo, tenant_id=tenant_id, user_id=user_id, job_id=job_id)
    start_time = datetime.utcnow()

    processed = 0
    inserted = 0
    updated = 0
    ignored = 0
    errors = 0
    logs_buffer: list[dict] = []

    try:
        page = 1
        while processed < _ITEMS_TO_FETCH:
            payload = _discover(tipo, page=page)
            results = payload.get("results", [])
            if not results:
                break
            for result in results:
                if processed >= _ITEMS_TO_FETCH:
                    break
                tmdb_id = result.get("id")
                if not tmdb_id:
                    ignored += 1
                    processed += 1
                    continue
                try:
                    details = _fetch_details(tipo, tmdb_id)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.exception("Falha ao buscar detalhes TMDb %s: %s", tmdb_id, exc)
                    errors += 1
                    processed += 1
                    logs_buffer.append(
                        {
                            "kind": "item",
                            "tmdb_id": tmdb_id,
                            "status": "error",
                            "message": str(exc),
                        }
                    )
                    continue

                title = details.get("title") or details.get("name") or result.get("title") or result.get("name")
                year = _extract_year(details or result)
                genres = _genre_names(tipo, details if details.get("genres") else result)

                logs_buffer.append(
                    {
                        "kind": "item",
                        "tmdb_id": tmdb_id,
                        "title": title,
                        "year": year,
                        "genres": genres,
                        "status": "inserted",
                    }
                )
                inserted += 1
                processed += 1

                if len(logs_buffer) >= _PROGRESS_CHUNK:
                    _persist_logs(job, logs_buffer)
                    logs_buffer.clear()

                if processed % _PROGRESS_CHUNK == 0 or processed == _ITEMS_TO_FETCH:
                    job.progress = processed / _ITEMS_TO_FETCH
                    job.inserted = inserted
                    job.updated = updated
                    job.ignored = ignored
                    job.errors = errors
                    job.eta_sec = _estimate_eta(start_time, processed)
                    db.session.commit()

            page += 1

        if logs_buffer:
            _persist_logs(job, logs_buffer)
            logs_buffer.clear()

        job.status = JobStatus.FINISHED
        job.progress = 1.0
        job.inserted = inserted
        job.updated = updated
        job.ignored = ignored
        job.errors = errors
        job.finished_at = datetime.utcnow()
        job.duration_sec = int((job.finished_at - job.started_at).total_seconds()) if job.started_at else None
        job.eta_sec = None

        summary = {
            "kind": "summary",
            "totals": {
                "inserted": inserted,
                "updated": updated,
                "ignored": ignored,
                "errors": errors,
            },
            "durationSec": job.duration_sec,
        }
        db.session.add(JobLog(job_id=job.id, content=json.dumps(summary, ensure_ascii=False)))
        db.session.commit()

    except Exception as exc:  # pragma: no cover - defensive
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
                job.errors = errors + 1
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
