from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .importers import limpar_nome

_EXTINF_PATTERN = re.compile(r"#EXTINF:-?\d+\s*(?P<attrs>[^,]*),(?P<title>.*)")
_ATTR_PATTERN = re.compile(r"(?P<key>[a-zA-Z0-9_-]+)\s*=\s*\"(?P<value>[^\"]*)\"")
_SERIES_TOKEN = re.compile(r"S(?P<season>\d{1,2})E(?P<episode>\d{1,2})", re.IGNORECASE)
_PREFIX_STRIP = re.compile(r"^[\s\-:|>]+|[\s\-:|>]+$")


@dataclass
class MovieCandidate:
    title: str
    category: Optional[str]
    urls: list[str]
    origin: str
    tmdb_id: Optional[int] = None


@dataclass
class SeriesEpisodeCandidate:
    title: str
    title_base: str
    season: int
    episode: int
    category: Optional[str]
    urls: list[str]
    origin: str
    tmdb_id: Optional[int] = None


def _parse_extinf(line: str) -> tuple[dict[str, str], str]:
    match = _EXTINF_PATTERN.match(line.strip())
    if not match:
        return {}, line.strip().split(",", 1)[-1].strip()
    attrs = match.group("attrs")
    title = match.group("title").strip()
    metadata: dict[str, str] = {}
    for attr_match in _ATTR_PATTERN.finditer(attrs):
        key = attr_match.group("key").lower()
        metadata[key] = attr_match.group("value")
    return metadata, title


def _normalize_urls(urls: Iterable[str]) -> list[str]:
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


def _normalize_category(category: Optional[str]) -> Optional[str]:
    if not category:
        return None
    normalized = category.strip()
    lowered = normalized.lower()
    for prefix in ("series", "canais", "canal"):
        if lowered.startswith(prefix):
            normalized = normalized[len(prefix) :].strip(" -:/") or normalized
            break
    return normalized or None


def iter_movies_from_m3u(path: str | Path) -> Iterator[MovieCandidate]:
    file_path = Path(path)
    if not file_path.exists():
        return iter(())
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return iter(())

    def _generator() -> Iterator[MovieCandidate]:
        iterator = iter(content)
        for line in iterator:
            if not line or not line.lstrip().startswith("#EXTINF"):
                continue
            metadata, title = _parse_extinf(line)
            try:
                url = next(iterator).strip()
            except StopIteration:
                break
            urls = _normalize_urls([url])
            if not urls:
                continue
            category = _normalize_category(metadata.get("group-title") or metadata.get("group_title"))
            yield MovieCandidate(
                title=limpar_nome(title) or title.strip(),
                category=category,
                urls=urls,
                origin=f"m3u:{file_path.name}",
            )

    return _generator()


def _extract_episode_tokens(raw_title: str) -> tuple[str, int, int, str]:
    match = _SERIES_TOKEN.search(raw_title)
    if not match:
        cleaned = limpar_nome(raw_title) or raw_title.strip()
        return cleaned, 1, 1, cleaned
    season = int(match.group("season"))
    episode = int(match.group("episode"))
    prefix = raw_title[: match.start()].strip()
    suffix = raw_title[match.end() :].strip()
    title_base = limpar_nome(_PREFIX_STRIP.sub("", prefix)) or limpar_nome(raw_title)
    episode_title = limpar_nome(_PREFIX_STRIP.sub("", suffix)) or limpar_nome(raw_title)
    return title_base or raw_title.strip(), season, episode, episode_title or raw_title.strip()


def iter_series_from_m3u(path: str | Path) -> Iterator[SeriesEpisodeCandidate]:
    file_path = Path(path)
    if not file_path.exists():
        return iter(())
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return iter(())

    def _generator() -> Iterator[SeriesEpisodeCandidate]:
        iterator = iter(content)
        for line in iterator:
            if not line or not line.lstrip().startswith("#EXTINF"):
                continue
            metadata, raw_title = _parse_extinf(line)
            try:
                url = next(iterator).strip()
            except StopIteration:
                break
            urls = _normalize_urls([url])
            if not urls:
                continue
            title_base, season, episode, episode_title = _extract_episode_tokens(raw_title)
            category = metadata.get("group-title") or metadata.get("group_title")
            yield SeriesEpisodeCandidate(
                title=episode_title,
                title_base=title_base or limpar_nome(raw_title) or raw_title.strip(),
                season=season,
                episode=episode,
                category=category.strip() if category else None,
                urls=urls,
                origin=f"m3u:{file_path.name}",
            )

    return _generator()


__all__ = [
    "MovieCandidate",
    "SeriesEpisodeCandidate",
    "iter_movies_from_m3u",
    "iter_series_from_m3u",
]
