"""Utilities for parsing M3U links used to configure XUI credentials."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse


_M3U_REGEX = re.compile(
    r"https?://([^:/]+)(?::(\d+))?.*username=([^&]+).*password=([^&]+)",
    re.IGNORECASE,
)


def parse_m3u_link(link: str) -> dict[str, Any] | None:
    """Extract domain, port, username and password from an M3U link."""

    if not isinstance(link, str):
        return None

    candidate = link.strip()
    if not candidate:
        return None

    try:
        match = _M3U_REGEX.search(candidate)
        if not match:
            parsed = urlparse(candidate)
            query = parse_qs(parsed.query)
            username_values = query.get("username")
            password_values = query.get("password")
            if not username_values or not password_values:
                return None
            username = username_values[0]
            password = password_values[0]
            host = parsed.hostname or ""
            port = parsed.port or 80
        else:
            host, port_text, username, password = match.groups()
            port = int(port_text or 80)

        username = username.strip()
        password = password.strip()
        host = host.strip()
        if not host or not username or not password:
            return None

        return {
            "domain": host,
            "port": int(port) if port else 80,
            "username": username,
            "password": password,
            "xuiDbUri": f"mysql+pymysql://{username}:{password}@{host}:3306/xui",
        }
    except Exception:
        return None
