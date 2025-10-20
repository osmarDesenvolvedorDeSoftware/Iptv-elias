"""Celery tasks package."""

# Ensure task modules are imported when Celery discovers ``app.tasks``
# so that decorators run and tasks become registered.
from .importers import run_import  # noqa: F401
from .normalization import normalize_xui_sources  # noqa: F401
