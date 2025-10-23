"""Utility helpers for database-related operations."""

from __future__ import annotations

import re
import urllib.parse


def safe_encode_password(password: str) -> str:
    """Encode a password for inclusion in URIs without double-encoding."""

    if not password:
        return ""
    if re.search(r"%[0-9A-Fa-f]{2}", password):
        return password
    return urllib.parse.quote_plus(password)
