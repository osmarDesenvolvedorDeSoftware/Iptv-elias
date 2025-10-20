from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .importers import normalize_stream_source, source_tag_from_url


@dataclass
class StreamNormalizationSummary:
    total: int = 0
    updated: int = 0
    movies_tagged: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "updated": self.updated,
            "moviesTagged": self.movies_tagged,
        }


@dataclass
class SeriesNormalizationSummary:
    total: int = 0
    tagged: int = 0
    episodes_analyzed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "tagged": self.tagged,
            "episodesAnalyzed": self.episodes_analyzed,
        }


@dataclass
class NormalizationResult:
    streams: StreamNormalizationSummary
    series: SeriesNormalizationSummary

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {
            "streams": self.streams.to_dict(),
            "series": self.series.to_dict(),
        }

    def to_log_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": "normalization",
            "streams": self.streams.to_dict(),
            "series": self.series.to_dict(),
        }
        return payload


def _normalize_stream_source_value(value: str | None) -> tuple[list[str], str | None, bool]:
    if value is None or value == "":
        return [], None, False

    changed = False

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        parsed = value
        changed = True

    values: Iterable[str] | str | None
    if isinstance(parsed, list):
        values = parsed
    elif isinstance(parsed, str):
        values = [parsed]
        changed = True
    else:
        values = []
        changed = True

    candidates: list[str] = []
    non_string_found = False
    trimmed_detected = False
    empty_detected = False
    duplicates_detected = False
    seen: set[str] = set()

    for item in values:
        if not isinstance(item, str):
            non_string_found = True
            continue
        trimmed = item.strip()
        if trimmed != item:
            trimmed_detected = True
        if not trimmed:
            empty_detected = True
            continue
        if trimmed in seen:
            duplicates_detected = True
            continue
        seen.add(trimmed)
        candidates.append(trimmed)

    normalized = normalize_stream_source(candidates)

    if non_string_found or trimmed_detected or empty_detected or duplicates_detected:
        changed = True
    if len(normalized) != len(candidates):
        changed = True

    first_url = normalized[0] if normalized else None
    return normalized, first_url, changed


def _normalize_streams(connection: Connection) -> StreamNormalizationSummary:
    summary = StreamNormalizationSummary()

    query = text(
        """
        SELECT id, type, stream_source, source_tag_filmes
        FROM streams
        """
    )
    rows = connection.execute(query).mappings()

    update_stream_source = text(
        """
        UPDATE streams
        SET stream_source = :stream_source
        WHERE id = :id
        """
    )
    update_movie_tag = text(
        """
        UPDATE streams
        SET source_tag_filmes = :tag
        WHERE id = :id
        """
    )

    for row in rows:
        summary.total += 1
        stream_id = row["id"]
        stream_type = row.get("type")
        try:
            stream_type_int = int(stream_type)
        except (TypeError, ValueError):
            stream_type_int = None

        normalized, first_url, changed = _normalize_stream_source_value(row.get("stream_source"))
        if changed:
            payload = json.dumps(normalized, ensure_ascii=False)
            connection.execute(update_stream_source, {"stream_source": payload, "id": stream_id})
            summary.updated += 1

        if stream_type_int == 2:
            current_tag = row.get("source_tag_filmes") or ""
            if not current_tag.strip() and first_url:
                tag = source_tag_from_url(first_url)
                if tag:
                    connection.execute(update_movie_tag, {"tag": tag, "id": stream_id})
                    summary.movies_tagged += 1

    return summary


def _normalize_series(connection: Connection) -> SeriesNormalizationSummary:
    summary = SeriesNormalizationSummary()

    series_rows = connection.execute(
        text(
            """
            SELECT id, source_tag
            FROM streams_series
            """
        )
    ).mappings()

    update_series_tag = text(
        """
        UPDATE streams_series
        SET source_tag = :tag
        WHERE id = :id
        """
    )

    for series in series_rows:
        summary.total += 1
        current_tag = series.get("source_tag") or ""
        if current_tag.strip():
            continue

        series_id = series["id"]
        episodes = connection.execute(
            text(
                """
                SELECT s.stream_source
                FROM streams_episodes AS se
                JOIN streams AS s ON s.id = se.stream_id
                WHERE se.series_id = :series_id AND s.type = 5
                """
            ),
            {"series_id": series_id},
        ).mappings()

        counter: Counter[str] = Counter()
        for episode in episodes:
            summary.episodes_analyzed += 1
            normalized, first_url, _ = _normalize_stream_source_value(episode.get("stream_source"))
            if not first_url:
                continue
            tag = source_tag_from_url(first_url)
            if not tag:
                continue
            counter[tag] += 1

        if not counter:
            continue

        major_tag, _ = counter.most_common(1)[0]
        connection.execute(update_series_tag, {"tag": major_tag, "id": series_id})
        summary.tagged += 1

    return summary


def normalize_sources(connection: Connection) -> NormalizationResult:
    streams_summary = _normalize_streams(connection)
    series_summary = _normalize_series(connection)
    return NormalizationResult(streams=streams_summary, series=series_summary)


__all__ = [
    "NormalizationResult",
    "SeriesNormalizationSummary",
    "StreamNormalizationSummary",
    "normalize_sources",
]
