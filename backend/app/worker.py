"""Standalone Celery worker entrypoint.

This module allows running the worker with ``python -m app.worker`` so the
application does not rely on ``celery`` CLI discovery of ``app.celery_app``.
It mirrors the configuration produced by :func:`app.extensions.init_celery`
and honours environment variables for log level, queues and concurrency.
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

from .extensions import celery_app, init_celery


def _has_flag(argv: Iterable[str], short_flag: str, long_flag: str) -> bool:
    for item in argv:
        if item == short_flag or item == long_flag or item.startswith(f"{long_flag}="):
            return True
    return False


def _ensure_option(argv: list[str], short_flag: str, long_flag: str, value: str | None) -> list[str]:
    """Insert default options when they were not provided explicitly."""

    if value is None or _has_flag(argv, short_flag, long_flag):
        return argv

    return [short_flag, value, *argv]


def main(raw_args: list[str] | None = None) -> None:
    """Bootstrap Celery and hand over execution to the worker."""

    init_celery()

    args = list(raw_args if raw_args is not None else sys.argv[1:])

    # Respect optional environment overrides but keep sensible defaults.
    args = _ensure_option(args, "-l", "--loglevel", os.getenv("CELERY_LOG_LEVEL", "info"))
    args = _ensure_option(args, "-Q", "--queues", os.getenv("CELERY_QUEUES"))
    args = _ensure_option(args, "-c", "--concurrency", os.getenv("CELERY_CONCURRENCY"))

    celery_app.worker_main(["worker", *args])


if __name__ == "__main__":
    main()
