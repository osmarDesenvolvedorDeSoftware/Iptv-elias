from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.tasks.importers import _MovieImporter, _is_adult, _normalize_int, _sanitize_tmdb_query


class DummyJob:
    def __init__(self) -> None:
        self.progress = 0.0
        self.inserted = 0
        self.ignored = 0
        self.errors = 0
        self.eta_sec = None
        self.source_tag = None
        self.source_tag_filmes = None


@pytest.fixture()
def movie_importer_setup():
    job = DummyJob()
    repository = MagicMock()
    repository.movie_url_exists.side_effect = [None, {"id": 99, "source_tag_filmes": "example.com"}]
    repository.insert_movie.return_value = 10
    xtream = MagicMock()
    xtream.base_url = "http://vod.example"
    xtream.username = "user"
    xtream.password = "pass"
    xtream.vod_streams.return_value = [
        {
            "stream_id": 1,
            "name": "Matrix",
            "category_id": "5",
            "container_extension": "mp4",
            "stream_icon": "",
        },
        {
            "stream_id": 2,
            "name": "Matrix",
            "category_id": "5",
            "container_extension": "mp4",
            "stream_icon": "",
        },
    ]
    xtream.vod_categories.return_value = [{"category_id": "5", "category_name": "Ação"}]
    options = {
        "categoryMapping": {"movies": {"5": 15}},
        "bouquets": {"movies": 3, "adult": None},
        "tmdb": {"enabled": False, "apiKey": None, "language": "pt-BR", "region": "BR"},
        "adultKeywords": [],
        "adultCategories": [],
        "retry": {"enabled": True, "maxAttempts": 3, "backoffSeconds": 1},
        "throttleMs": 0,
        "limitItems": None,
        "maxParallel": 1,
        "ignore": {
            "movies": {"categories": [], "prefixes": []},
            "series": {"categories": [], "prefixes": []},
        },
    }
    importer = _MovieImporter(job=job, tenant_id="tenant1", repository=repository, xtream=xtream, options=options)
    return job, repository, importer


def test_normalize_int():
    assert _normalize_int("5") == 5
    assert _normalize_int(7) == 7
    assert _normalize_int("invalid") is None
    assert _normalize_int(None) is None


def test_is_adult_detection():
    options = {"adultKeywords": ["xxx"], "adultCategories": ["9"]}
    assert _is_adult("Filme XXX", None, None, options)
    assert _is_adult("Filme", "Categoria xxx", None, options)
    assert _is_adult("Filme", None, "9", options)
    assert not _is_adult("Filme", "Ação", "1", options)


def test_sanitize_tmdb_query():
    assert _sanitize_tmdb_query("Matrix - 1999") == "Matrix"
    assert _sanitize_tmdb_query("Matrix (1999)") == "Matrix"
    assert _sanitize_tmdb_query("  Matrix Reloaded  ") == "Matrix Reloaded"


@patch("app.tasks.importers.db.session.commit")
@patch("app.tasks.importers.db.session.add_all")
@patch("app.tasks.importers.db.session.flush")
def test_movie_importer_deduplicates(mock_flush, mock_add_all, mock_commit, movie_importer_setup):
    job, repository, importer = movie_importer_setup

    importer.execute()

    assert repository.insert_movie.call_count == 1
    assert repository.movie_url_exists.call_count == 2
    assert job.inserted == 1
    assert job.updated >= 1
    assert job.source_tag_filmes is not None


@patch("app.tasks.importers.db.session.commit")
@patch("app.tasks.importers.db.session.add_all")
@patch("app.tasks.importers.db.session.flush")
def test_movie_importer_ignores_by_prefix(mock_flush, mock_add_all, mock_commit):
    job = DummyJob()
    repository = MagicMock()
    repository.movie_url_exists.return_value = None
    xtream = MagicMock()
    xtream.base_url = "http://vod.example"
    xtream.username = "user"
    xtream.password = "pass"
    xtream.vod_streams.return_value = [
        {
            "stream_id": 1,
            "name": "Matrix Reloaded",
            "category_id": "5",
            "container_extension": "mp4",
            "stream_icon": "",
        }
    ]
    xtream.vod_categories.return_value = [{"category_id": "5", "category_name": "Ação"}]
    options = {
        "categoryMapping": {"movies": {"5": 15}},
        "bouquets": {"movies": 3, "adult": None},
        "tmdb": {"enabled": False, "apiKey": None, "language": "pt-BR", "region": "BR"},
        "adultKeywords": [],
        "adultCategories": [],
        "retry": {"enabled": True, "maxAttempts": 3, "backoffSeconds": 1},
        "throttleMs": 0,
        "limitItems": None,
        "maxParallel": 1,
        "ignore": {
            "movies": {"categories": [], "prefixes": ["Matrix"]},
            "series": {"categories": [], "prefixes": []},
        },
    }
    importer = _MovieImporter(job=job, tenant_id="tenant1", repository=repository, xtream=xtream, options=options)

    importer.execute()

    repository.insert_movie.assert_not_called()
    repository.movie_url_exists.assert_not_called()
    assert job.inserted == 0
    assert job.ignored == 1
