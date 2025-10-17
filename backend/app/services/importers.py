"""Utilidades compartilhadas entre os importadores e compatíveis com os scripts legados."""

from __future__ import annotations

import re
from typing import Iterable
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

_EXTENSION_PATTERN = re.compile(r"\.(mkv|mp4|avi|mov|wmv|m3u8)$", re.IGNORECASE)
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


__all__ = ["categoria_adulta", "limpar_nome", "dominio_de"]
