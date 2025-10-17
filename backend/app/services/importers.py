"""Utilidades compartilhadas entre os importadores e compatíveis com os scripts legados."""

from __future__ import annotations

import re
from typing import Iterable, Sequence
from urllib.parse import urlparse

_ADULT_KEYWORDS = {
    "adult",
    "xxx",
    "porn",
    "erotic",
    "sensual",
    "+18",
    "nsfw",
}

_EXTENSION_PATTERN = re.compile(r"\.(mkv|mp4|avi|mov|wmv|m3u8|ts)$", re.IGNORECASE)
_CLEANUP_BRACKETS = re.compile(r"\s*[\[\(][^\]\)]*[\)\]]\s*")
_MULTISPACE_PATTERN = re.compile(r"\s{2,}")
_SYMBOLS_PATTERN = re.compile(r"[\-_]+")


def categoria_adulta(title: str | None = None, genres: Iterable[str] | None = None) -> bool:
    """Determina se um conteúdo deve ser tratado como adulto."""

    if genres:
        for genre in genres:
            if genre and genre.strip().lower() in {"adult", "erotica"}:
                return True
    if not title:
        return False
    lower = title.lower()
    return any(keyword in lower for keyword in _ADULT_KEYWORDS)


def limpar_nome(name: str | None) -> str:
    """Remove sufixos comuns e normaliza espaços, preservando compatibilidade com o legado."""

    if not name:
        return ""
    cleaned = _EXTENSION_PATTERN.sub("", name)
    cleaned = _CLEANUP_BRACKETS.sub(" ", cleaned)
    cleaned = _SYMBOLS_PATTERN.sub(" ", cleaned)
    cleaned = _MULTISPACE_PATTERN.sub(" ", cleaned)
    return cleaned.strip()


def dominio_de(url: str | None) -> str | None:
    """Extrai o domínio a partir de uma URL completa ou parcial."""

    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"http://{url}")
    hostname = parsed.hostname or ""
    return hostname.lower() or None


def source_tag_from_url(url: str | None) -> str | None:
    """Retorna a tag de origem no formato dominio[:porta]."""

    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"http://{url}")
    if not parsed.hostname:
        return None
    hostname = parsed.hostname.lower()
    if parsed.port:
        return f"{hostname}:{parsed.port}"
    return hostname


def normalize_stream_source(urls: Sequence[str | None]) -> list[str]:
    """Garante compatibilidade do campo stream_source do legado."""

    normalized: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url:
            continue
        cleaned = url.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def target_container_from_url(url: str | None) -> str | None:
    """Detecta o container baseado na extensão do arquivo."""

    if not url:
        return None
    match = _EXTENSION_PATTERN.search(url)
    if not match:
        return None
    return match.group(1).lower()


__all__ = [
    "categoria_adulta",
    "limpar_nome",
    "dominio_de",
    "source_tag_from_url",
    "normalize_stream_source",
    "target_container_from_url",
]
