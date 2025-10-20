from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .xui_normalizer import NormalizationResult, normalize_sources

_engine_registry: dict[str, Engine] = {}
_registry_lock = threading.Lock()


@dataclass
class XuiCredentials:
    uri: str


def get_engine(tenant_id: str, credentials: XuiCredentials) -> Engine:
    if not credentials.uri:
        raise RuntimeError("URI do banco XUI não configurada")

    with _registry_lock:
        engine = _engine_registry.get(tenant_id)
        if engine is None:
            engine = create_engine(credentials.uri, pool_pre_ping=True, pool_recycle=3600)
            _engine_registry[tenant_id] = engine
        return engine


def dispose_engine(tenant_id: str) -> None:
    with _registry_lock:
        engine = _engine_registry.pop(tenant_id, None)
        if engine is not None:
            engine.dispose()


@contextmanager
def session_scope(engine: Engine) -> Iterator[Any]:
    connection = engine.connect()
    transaction = connection.begin()
    try:
        yield connection
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        connection.close()


class XuiRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._database_name: str | None = None

    def _database(self, connection) -> str:
        if self._database_name:
            return self._database_name
        result = connection.execute(text("SELECT DATABASE()"))
        value = result.scalar()
        if not value:
            raise RuntimeError("Não foi possível identificar o schema do XUI")
        self._database_name = value
        return value

    def ensure_compatibility(self) -> None:
        with session_scope(self.engine) as conn:
            schema = self._database(conn)
            self._ensure_column(conn, schema, "streams", "source_tag_filmes", "ALTER TABLE `streams` ADD COLUMN `source_tag_filmes` VARCHAR(255) NULL")
            self._ensure_column(conn, schema, "streams_series", "source_tag", "ALTER TABLE `streams_series` ADD COLUMN `source_tag` VARCHAR(255) NULL")

    def _ensure_column(self, connection, schema: str, table: str, column: str, ddl: str) -> None:
        query = text(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table AND COLUMN_NAME = :column
            """
        )
        result = connection.execute(query, {"schema": schema, "table": table, "column": column})
        exists = result.scalar() or 0
        if not exists:
            connection.execute(text(ddl))

    def normalize_stream_sources(self) -> NormalizationResult:
        with session_scope(self.engine) as conn:
            result = normalize_sources(conn)
            return result

    def movie_url_exists(self, url: str) -> Mapping[str, Any] | None:
        query = text(
            """
            SELECT id, source_tag_filmes FROM streams
            WHERE type = 2 AND JSON_CONTAINS(stream_source, JSON_QUOTE(:url))
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            result = conn.execute(query, {"url": url})
            row = result.mappings().first()
            return row

    def episode_url_exists(self, url: str) -> bool:
        query = text(
            """
            SELECT 1 FROM streams
            WHERE JSON_CONTAINS(stream_source, JSON_QUOTE(:url))
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            result = conn.execute(query, {"url": url})
            return result.first() is not None

    def insert_movie(
        self,
        *,
        title: str,
        category_id: int,
        urls: Iterable[str],
        icon: str | None,
        target_container: str | None,
        properties: Mapping[str, Any] | None,
        source_tag: str | None,
    ) -> int:
        payload = {
            "category_id": json.dumps([category_id]) if category_id else json.dumps([]),
            "stream_display_name": title,
            "stream_source": json.dumps(list(urls), ensure_ascii=False),
            "stream_icon": icon or "",
            "type": 2,
            "movie_properties": json.dumps(properties or {}, ensure_ascii=False),
            "direct_source": 1,
            "target_container": target_container,
            "source_tag_filmes": source_tag,
        }
        statement = text(
            """
            INSERT INTO streams
                (category_id, stream_display_name, stream_source, stream_icon, type,
                 movie_properties, direct_source, target_container, source_tag_filmes)
            VALUES
                (:category_id, :stream_display_name, :stream_source, :stream_icon, :type,
                 :movie_properties, :direct_source, :target_container, :source_tag_filmes)
            """
        )
        with session_scope(self.engine) as conn:
            result = conn.execute(statement, payload)
            stream_id = result.lastrowid
            return int(stream_id)

    def append_movie_to_bouquet(self, bouquet_id: int, stream_id: int) -> None:
        if not bouquet_id:
            return
        with session_scope(self.engine) as conn:
            current = conn.execute(
                text("SELECT bouquet_movies FROM bouquets WHERE id = :id FOR UPDATE"),
                {"id": bouquet_id},
            ).scalar()
            try:
                movies = json.loads(current) if current else []
            except (ValueError, TypeError):
                movies = []
            if stream_id not in movies:
                movies.append(stream_id)
                conn.execute(
                    text("UPDATE bouquets SET bouquet_movies = :payload WHERE id = :id"),
                    {"payload": json.dumps(movies), "id": bouquet_id},
                )

    def fetch_series(self, title: str, source_tag: str | None) -> Mapping[str, Any] | None:
        query = text(
            """
            SELECT id, source_tag FROM streams_series
            WHERE title = :title AND (:tag IS NULL OR source_tag = :tag)
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            result = conn.execute(query, {"title": title, "tag": source_tag})
            row = result.mappings().first()
            if row:
                return row
            if source_tag:
                fallback = conn.execute(
                    text(
                        """
                        SELECT id, source_tag FROM streams_series
                        WHERE title = :title AND (source_tag IS NULL OR source_tag = '')
                        LIMIT 1
                        """
                    ),
                    {"title": title},
                ).mappings().first()
                if fallback:
                    conn.execute(
                        text("UPDATE streams_series SET source_tag = :tag WHERE id = :id"),
                        {"tag": source_tag, "id": fallback["id"]},
                    )
                    return {"id": fallback["id"], "source_tag": source_tag}
            return None

    def create_series(
        self,
        *,
        title: str,
        category_id: int,
        cover: str | None,
        backdrop: str | None,
        plot: str | None,
        rating: float | None,
        tmdb_language: str,
        source_tag: str | None,
    ) -> int:
        payload = {
            "title": title,
            "category_id": json.dumps([category_id]) if category_id else json.dumps([]),
            "cover": cover or "",
            "cover_big": cover or "",
            "backdrop_path": json.dumps([backdrop] if backdrop else []),
            "plot": plot or "",
            "cast": "",
            "rating": rating,
            "youtube_trailer": "",
            "tmdb_language": tmdb_language,
            "source_tag": source_tag,
        }
        statement = text(
            """
            INSERT INTO streams_series
                (title, category_id, cover, cover_big, backdrop_path, plot, cast,
                 rating, youtube_trailer, tmdb_language, source_tag)
            VALUES
                (:title, :category_id, :cover, :cover_big, :backdrop_path, :plot, :cast,
                 :rating, :youtube_trailer, :tmdb_language, :source_tag)
            """
        )
        with session_scope(self.engine) as conn:
            result = conn.execute(statement, payload)
            return int(result.lastrowid)

    def append_series_to_bouquet(self, bouquet_id: int, series_id: int) -> None:
        if not bouquet_id:
            return
        with session_scope(self.engine) as conn:
            current = conn.execute(
                text("SELECT bouquet_series FROM bouquets WHERE id = :id FOR UPDATE"),
                {"id": bouquet_id},
            ).scalar()
            try:
                series = json.loads(current) if current else []
            except (ValueError, TypeError):
                series = []
            if series_id not in series:
                series.append(series_id)
                conn.execute(
                    text("UPDATE bouquets SET bouquet_series = :payload WHERE id = :id"),
                    {"payload": json.dumps(series), "id": bouquet_id},
                )

    def insert_episode(
        self,
        *,
        stream_title: str,
        urls: Iterable[str],
        icon: str | None,
        target_container: str | None,
        properties: Mapping[str, Any] | None,
        series_id: int,
        season: int,
        episode: int,
        source_tag: str | None,
    ) -> int:
        stream_payload = {
            "stream_display_name": stream_title,
            "stream_source": json.dumps(list(urls), ensure_ascii=False),
            "stream_icon": icon or "",
            "type": 5,
            "movie_properties": json.dumps(properties or {}, ensure_ascii=False),
            "direct_source": 1,
            "target_container": target_container,
            "source_tag": source_tag,
        }
        insert_stream = text(
            """
            INSERT INTO streams
                (stream_display_name, stream_source, stream_icon, type,
                 movie_properties, direct_source, target_container, source_tag)
            VALUES
                (:stream_display_name, :stream_source, :stream_icon, :type,
                 :movie_properties, :direct_source, :target_container, :source_tag)
            """
        )
        insert_episode = text(
            """
            INSERT INTO streams_episodes (season_num, episode_num, series_id, stream_id)
            VALUES (:season_num, :episode_num, :series_id, :stream_id)
            """
        )
        with session_scope(self.engine) as conn:
            result = conn.execute(insert_stream, stream_payload)
            stream_id = int(result.lastrowid)
            conn.execute(
                insert_episode,
                {
                    "season_num": season,
                    "episode_num": episode,
                    "series_id": series_id,
                    "stream_id": stream_id,
                },
            )
            return stream_id


__all__ = [
    "XuiCredentials",
    "get_engine",
    "dispose_engine",
    "XuiRepository",
]
