"""TMDb API integration helpers."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import requests

from ..config import Config

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.themoviedb.org/3"
_config = Config()
_session = requests.Session()


def _build_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "api_key": _config.TMDB_API_KEY,
        "language": _config.TMDB_LANGUAGE,
        "region": _config.TMDB_REGION,
    }
    if extra:
        params.update(extra)
    return params


def _request(method: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _config.TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY não configurada")

    url = f"{_BASE_URL}{path}"
    response = _session.request(method, url, params=_build_params(params))
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.exception("Erro ao chamar TMDb: %s", response.text)
        raise
    return response.json()


def search_movies(query: str, page: int = 1, include_adult: bool = False) -> dict[str, Any]:
    """Busca filmes pelo termo informado."""

    return _request(
        "GET",
        "/search/movie",
        {
            "query": query,
            "page": page,
            "include_adult": include_adult,
        },
    )


def search_series(query: str, page: int = 1) -> dict[str, Any]:
    """Busca séries pelo termo informado."""

    return _request(
        "GET",
        "/search/tv",
        {
            "query": query,
            "page": page,
        },
    )


def fetch_movie_details(tmdb_id: int) -> dict[str, Any]:
    """Recupera os detalhes de um filme pelo identificador TMDb."""

    return _request("GET", f"/movie/{tmdb_id}")


def fetch_series_details(tmdb_id: int) -> dict[str, Any]:
    """Recupera os detalhes de uma série pelo identificador TMDb."""

    return _request("GET", f"/tv/{tmdb_id}")


def discover_movies(page: int = 1) -> dict[str, Any]:
    """Descobre filmes populares respeitando idioma/região configurados."""

    return _request(
        "GET",
        "/discover/movie",
        {
            "page": page,
            "sort_by": "popularity.desc",
        },
    )


def discover_series(page: int = 1) -> dict[str, Any]:
    """Descobre séries populares respeitando idioma/região configurados."""

    return _request(
        "GET",
        "/discover/tv",
        {
            "page": page,
            "sort_by": "popularity.desc",
        },
    )


@lru_cache(maxsize=1)
def movie_genres() -> dict[int, str]:
    """Mapeamento de IDs para nomes de gêneros de filmes."""

    payload = _request("GET", "/genre/movie/list")
    return {genre["id"]: genre["name"] for genre in payload.get("genres", [])}


@lru_cache(maxsize=1)
def series_genres() -> dict[int, str]:
    """Mapeamento de IDs para nomes de gêneros de séries."""

    payload = _request("GET", "/genre/tv/list")
    return {genre["id"]: genre["name"] for genre in payload.get("genres", [])}


__all__ = [
    "search_movies",
    "search_series",
    "fetch_movie_details",
    "fetch_series_details",
    "discover_movies",
    "discover_series",
    "movie_genres",
    "series_genres",
]
