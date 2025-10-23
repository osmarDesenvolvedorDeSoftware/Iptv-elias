from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Mapping as MappingABC
from typing import Any, Iterable, Iterator, Mapping

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from .xui_normalizer import NormalizationResult, normalize_sources
from .mysql_errors import (
    MysqlAccessDeniedError,
    MysqlSslMisconfigurationError,
    is_access_denied_error,
    is_ssl_misconfiguration_error,
)

_engine_registry: dict[str, Engine] = {}
_engine_uri_registry: dict[str, str] = {}
_registry_lock = threading.Lock()


logger = logging.getLogger(__name__)


def _ensure_url(value: URL | str | None) -> URL | None:
    if value is None:
        return None
    if isinstance(value, URL):
        return value
    try:
        return make_url(value)
    except Exception:
        return None


def _render_safe_url(value: URL | str | None) -> str:
    if value is None:
        return "<nenhuma>"
    url = _ensure_url(value)
    if url is None:
        return str(value)
    try:
        return url.render_as_string(hide_password=True)
    except Exception:
        return str(value)


@dataclass
class XuiCredentials:
    uri: str


def _registry_key(tenant_id: str, user_id: int | None) -> str:
    suffix = str(user_id) if user_id is not None else "default"
    return f"{tenant_id}:{suffix}"


def get_engine(tenant_id: str, user_id: int | None, credentials: XuiCredentials) -> Engine:
    if not credentials.uri:
        raise RuntimeError("URI do banco XUI não configurada")

    masked_requested_uri = _render_safe_url(credentials.uri)

    with _registry_lock:
        key = _registry_key(tenant_id, user_id)
        engine = _engine_registry.get(key)
        current_uri = _engine_uri_registry.get(key)
        if engine is not None and current_uri == credentials.uri:
            try:
                cached_uri = _render_safe_url(engine.url)
            except Exception:
                cached_uri = masked_requested_uri
            logger.debug(
                "[XUI_DB] Reutilizando engine existente key=%s uri=%s",
                key,
                cached_uri,
            )
            return engine

        if engine is not None:
            logger.debug(
                "[XUI_DB] Substituindo engine existente key=%s uri_atual=%s nova_uri=%s",
                key,
                _render_safe_url(engine.url),
                masked_requested_uri,
            )
            engine.dispose()

        url = make_url(credentials.uri)
        driver = url.drivername
        logger.debug(
            "[XUI_DB] Inicializando nova engine key=%s driver=%s uri=%s",
            key,
            driver,
            masked_requested_uri,
        )
        if driver != "mysql+pymysql":
            logger.warning(
                "[XUI_DB] Driver inesperado para URI %s: %s",
                masked_requested_uri,
                driver,
            )
            new_engine: Engine | None = None
            try:
                new_engine = create_engine(
                    credentials.uri, pool_pre_ping=True, pool_recycle=3600
                )
                logger.debug(
                    "[XUI_DB] Engine criada key=%s pool_pre_ping=%s pool_recycle=%s",
                    key,
                    True,
                    3600,
                )
                with new_engine.connect() as connection:
                    logger.debug(
                        "[XUI_DB] Validando conexão inicial key=%s host=%s database=%s",
                        key,
                        url.host or "",
                        url.database or "",
                    )
                    connection.execute(text("SELECT 1"))
                    logger.debug(
                        "[XUI_DB] Validação inicial concluída key=%s",
                        key,
                    )
            except SQLAlchemyError as exc:
                if new_engine is not None:
                    new_engine.dispose()
                orig = getattr(exc, "orig", None)
                logger.debug(
                    "[XUI_DB] Falha ao inicializar engine key=%s driver=%s uri=%s exc=%s orig=%r orig_args=%r",
                    key,
                    driver,
                    masked_requested_uri,
                    exc.__class__.__name__,
                    orig,
                    getattr(orig, "args", ()),
                )
                if is_ssl_misconfiguration_error(exc):
                    logger.warning(
                        "[DB] Detected SSL misconfiguration on remote MySQL host %s (user=%s)",
                        url.host or "",
                        url.username or "",
                    )
                    raise MysqlSslMisconfigurationError(
                        host=url.host or "", user=url.username or ""
                    ) from exc
                if is_access_denied_error(exc):
                    logger.warning(
                        "[DB] Access denied on remote MySQL host %s (user=%s)",
                        url.host or "",
                        url.username or "",
                    )
                    raise MysqlAccessDeniedError(
                        host=url.host or "",
                        user=url.username or "",
                        database=url.database or "",
                    ) from exc
                raise
            engine = new_engine
            _engine_registry[key] = engine
            _engine_uri_registry[key] = credentials.uri
            logger.debug(
                "[XUI_DB] Engine registrada key=%s uri=%s",
                key,
                masked_requested_uri,
            )
        return engine


def dispose_engine(tenant_id: str, user_id: int | None = None) -> None:
    with _registry_lock:
        key = _registry_key(tenant_id, user_id)
        engine = _engine_registry.pop(key, None)
        _engine_uri_registry.pop(key, None)
        if engine is not None:
            logger.debug(
                "[XUI_DB] Descartando engine key=%s uri=%s",
                key,
                _render_safe_url(engine.url),
            )
            engine.dispose()
        else:
            logger.debug(
                "[XUI_DB] Nenhum engine em cache para descartar key=%s",
                key,
            )


@contextmanager
def session_scope(engine: Engine) -> Iterator[Any]:
    connection = _connect(engine)
    transaction = connection.begin()
    try:
        yield connection
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        connection.close()


def _connect(engine: Engine):
    logger.debug(
        "[XUI_DB] Abrindo conexão para engine uri=%s",
        _render_safe_url(engine.url),
    )
    try:
        return engine.connect()
    except SQLAlchemyError as exc:
        orig = getattr(exc, "orig", None)
        logger.debug(
            "[XUI_DB] Falha ao abrir conexão uri=%s exc=%s orig=%r orig_args=%r",
            _render_safe_url(engine.url),
            exc.__class__.__name__,
            orig,
            getattr(orig, "args", ()),
        )
        if is_ssl_misconfiguration_error(exc):
            url = engine.url
            logger.warning(
                "[DB] Detected SSL misconfiguration on remote MySQL host %s (user=%s)",
                url.host or "",
                url.username or "",
            )
            raise MysqlSslMisconfigurationError(
                host=url.host or "", user=url.username or ""
            ) from exc
        if is_access_denied_error(exc):
            url = engine.url
            logger.warning(
                "[DB] Access denied on remote MySQL host %s (user=%s)",
                url.host or "",
                url.username or "",
            )
            raise MysqlAccessDeniedError(
                host=url.host or "",
                user=url.username or "",
                database=url.database or "",
            ) from exc
        raise


class XuiRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._database_name: str | None = None

    def _serialize_categories(self, category_ids: Iterable[int]) -> str:
        normalized: list[int] = []
        seen: set[int] = set()
        for cid in category_ids:
            try:
                normalized_id = int(cid)
            except (TypeError, ValueError):
                continue
            if normalized_id in seen:
                continue
            seen.add(normalized_id)
            normalized.append(normalized_id)
        return json.dumps(normalized)

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

    def normalize_sources(self) -> NormalizationResult:
        with session_scope(self.engine) as conn:
            result = normalize_sources(conn)
            return result

    def movie_url_exists(self, url: str) -> Mapping[str, Any] | None:
        query = text(
            """
            SELECT id, category_id, stream_icon, target_container, movie_properties, source_tag_filmes
            FROM streams
            WHERE type = 2 AND JSON_CONTAINS(stream_source, JSON_QUOTE(:url))
            LIMIT 1
            """
        )
        with _connect(self.engine) as conn:
            result = conn.execute(query, {"url": url})
            row = result.mappings().first()
            if not row:
                return None
            try:
                categories = json.loads(row.get("category_id") or "[]")
            except (TypeError, ValueError):
                categories = []
            try:
                properties = json.loads(row.get("movie_properties") or "{}")
            except (TypeError, ValueError):
                properties = {}
            return {
                "id": int(row.get("id")),
                "category_ids": categories if isinstance(categories, list) else [],
                "stream_icon": row.get("stream_icon"),
                "target_container": row.get("target_container"),
                "movie_properties": properties if isinstance(properties, MappingABC) else {},
                "source_tag_filmes": row.get("source_tag_filmes"),
            }

    def episode_url_exists(self, url: str) -> Mapping[str, Any] | None:
        query = text(
            """
            SELECT id, category_id, stream_icon, target_container, movie_properties, source_tag
            FROM streams
            WHERE type = 5 AND JSON_CONTAINS(stream_source, JSON_QUOTE(:url))
            LIMIT 1
            """
        )
        with _connect(self.engine) as conn:
            result = conn.execute(query, {"url": url})
            row = result.mappings().first()
            if not row:
                return None
            try:
                categories = json.loads(row.get("category_id") or "[]")
            except (TypeError, ValueError):
                categories = []
            try:
                properties = json.loads(row.get("movie_properties") or "{}")
            except (TypeError, ValueError):
                properties = {}
            return {
                "id": int(row.get("id")),
                "category_ids": categories if isinstance(categories, list) else [],
                "stream_icon": row.get("stream_icon"),
                "target_container": row.get("target_container"),
                "movie_properties": properties if isinstance(properties, MappingABC) else {},
                "source_tag": row.get("source_tag"),
            }

    def update_movie_metadata(
        self,
        stream_id: int,
        *,
        category_ids: Iterable[int],
        icon: str | None,
        target_container: str | None,
        properties: Mapping[str, Any] | None,
        source_tag: str | None,
    ) -> None:
        payload = {
            "id": stream_id,
            "category_id": self._serialize_categories(category_ids),
            "stream_icon": icon or "",
            "target_container": target_container,
            "movie_properties": json.dumps(properties or {}, ensure_ascii=False),
            "source_tag_filmes": source_tag,
        }
        statement = text(
            """
            UPDATE streams
            SET category_id = :category_id,
                stream_icon = :stream_icon,
                target_container = :target_container,
                movie_properties = :movie_properties,
                source_tag_filmes = :source_tag_filmes
            WHERE id = :id
            """
        )
        with session_scope(self.engine) as conn:
            conn.execute(statement, payload)

    def update_episode_metadata(
        self,
        stream_id: int,
        *,
        category_ids: Iterable[int],
        icon: str | None,
        target_container: str | None,
        properties: Mapping[str, Any] | None,
        source_tag: str | None,
    ) -> None:
        payload = {
            "id": stream_id,
            "category_id": self._serialize_categories(category_ids),
            "stream_icon": icon or "",
            "target_container": target_container,
            "movie_properties": json.dumps(properties or {}, ensure_ascii=False),
            "source_tag": source_tag,
        }
        statement = text(
            """
            UPDATE streams
            SET category_id = :category_id,
                stream_icon = :stream_icon,
                target_container = :target_container,
                movie_properties = :movie_properties,
                source_tag = :source_tag
            WHERE id = :id
            """
        )
        with session_scope(self.engine) as conn:
            conn.execute(statement, payload)

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
        with _connect(self.engine) as conn:
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
