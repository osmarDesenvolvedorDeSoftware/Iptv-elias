"""Utilities for parsing M3U links used to configure XUI credentials."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse


LOGGER = logging.getLogger(__name__)


def parse_m3u_link(url: str) -> dict[str, str]:
    """Extract Xtream credentials from an M3U link."""

    if not isinstance(url, str):
        LOGGER.error("[M3U Parser] URL inválida: tipo %s", type(url).__name__)
        raise ValueError("M3U link inválido ou incompleto")

    candidate = url.strip()
    if not candidate:
        LOGGER.error("[M3U Parser] URL vazia fornecida")
        raise ValueError("M3U link inválido ou incompleto")

    parsed = urlparse(candidate)
    params = parse_qs(parsed.query)

    username_values = params.get("username")
    password_values = params.get("password")
    host = parsed.netloc.strip()

    if not host or not username_values or not password_values:
        LOGGER.error(
            "[M3U Parser] Dados incompletos: host=%s, username=%s, password=%s",
            host,
            bool(username_values),
            bool(password_values),
        )
        raise ValueError("M3U link inválido ou incompleto")

    username = username_values[0].strip()
    password = password_values[0].strip()
    if not username or not password:
        LOGGER.error(
            "[M3U Parser] Usuário ou senha vazios extraídos: username=%s", username
        )
        raise ValueError("M3U link inválido ou incompleto")

    credentials = {
        "host": host,
        "username": username,
        "password": password,
    }
    LOGGER.info("[M3U Parser] Host detectado: %s", host)
    return credentials
