from __future__ import annotations

import logging
import time
from typing import Any

import requests


logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://whmcss.top/",
}


class XtreamError(RuntimeError):
    pass


class XtreamClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout: int = 30,
        throttle_ms: int = 0,
        max_retries: int = 3,
        backoff_seconds: int = 5,
        max_parallel: int = 1,
        session: requests.Session | None = None,
    ) -> None:
        if not base_url or not username or not password:
            raise ValueError("Credenciais da API Xtream incompletas")
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.throttle_ms = throttle_ms
        self.max_retries = max(1, max_retries)
        self.backoff_seconds = max(1, backoff_seconds)
        self.max_parallel = max(1, max_parallel)
        self.session = session or requests.Session()
        self._throttle_counter = 0

    def _build_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Merge browser-like defaults with any session and per-request headers."""

        headers: dict[str, str] = dict(self.session.headers)
        headers.update(BROWSER_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        logger.debug("Xtream request headers merged: %s", headers)
        return headers

    def _perform_request(
        self,
        url: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str],
    ) -> requests.Response:
        response = self.session.get(url, params=params, timeout=self.timeout, headers=headers)
        if response.status_code >= 400:
            logger.warning(
                "Xtream request failed [%s]: %s",
                response.status_code,
                response.text[:200],
            )
        response.raise_for_status()
        return response

    def _call(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """Call Xtream's ``player_api.php`` handling Cloudflare mitigations.

        Some providers protect the endpoint with Cloudflare, which blocks plain HTTP
        clients unless the request mimics a real browser and uses HTTPS. This method
        applies realistic browser headers on every request and, when the configured
        base URL uses HTTP, automatically retries the same call via HTTPS once if the
        HTTP attempt is rejected with status 403.
        """
        query = {
            "username": self.username,
            "password": self.password,
            "action": action,
        }
        if params:
            query.update(params)
        url = f"{self.base_url}/player_api.php"
        https_base_url: str | None = None
        https_url: str | None = None
        if self.base_url.lower().startswith("http://"):
            rest = self.base_url.split("://", 1)[1]
            https_base_url = f"https://{rest}"
            https_url = f"{https_base_url}/player_api.php"

        headers = self._build_headers()
        last_error: requests.RequestException | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._perform_request(url, params=query, headers=headers)
                return response.json()
            except requests.HTTPError as exc:
                last_error = exc
                response = exc.response
                if (
                    https_url
                    and response is not None
                    and response.status_code == 403
                ):
                    logger.info(
                        "Xtream request received HTTP 403 for %s, retrying via HTTPS: %s",
                        url,
                        https_url,
                    )
                    try:
                        response = self._perform_request(https_url, params=query, headers=headers)
                        if https_base_url:
                            self.base_url = https_base_url
                            url = https_url
                            https_url = None
                        return response.json()
                    except requests.RequestException as https_exc:
                        last_error = https_exc
            except requests.RequestException as exc:
                last_error = exc

            if attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)

        raise XtreamError(
            f"Xtream API falhou após {self.max_retries} tentativas: {last_error}"
        ) from last_error

    def _throttle(self) -> None:
        if self.throttle_ms > 0:
            self._throttle_counter += 1
            if self._throttle_counter >= self.max_parallel:
                time.sleep(self.throttle_ms / 1000)
                self._throttle_counter = 0

    def vod_streams(self) -> list[dict[str, Any]]:
        payload = self._call("get_vod_streams")
        data: list[dict[str, Any]] = []
        if isinstance(payload, list):
            data = payload  # type: ignore[assignment]
        elif isinstance(payload, dict):
            streams = payload.get("available_channels")
            if isinstance(streams, list):
                data = streams  # type: ignore[assignment]
        self._throttle()
        return data

    def vod_categories(self) -> list[dict[str, Any]]:
        payload = self._call("get_vod_categories")
        data: list[dict[str, Any]] = []
        if isinstance(payload, list):
            data = payload  # type: ignore[assignment]
        elif isinstance(payload, dict):
            categories = payload.get("categories")
            if isinstance(categories, list):
                data = categories  # type: ignore[assignment]
        self._throttle()
        return data

    def series(self) -> list[dict[str, Any]]:
        payload = self._call("get_series")
        data: list[dict[str, Any]] = []
        if isinstance(payload, list):
            data = payload  # type: ignore[assignment]
        elif isinstance(payload, dict):
            series = payload.get("series")
            if isinstance(series, list):
                data = series  # type: ignore[assignment]
        self._throttle()
        return data

    def series_info(self, series_id: str | int) -> dict[str, Any]:
        payload = self._call("get_series_info", {"series_id": series_id})
        self._throttle()
        if isinstance(payload, dict):
            return payload
        raise XtreamError("Resposta inesperada de get_series_info")

    def vod_info(self, stream_id: str | int) -> dict[str, Any]:
        payload = self._call("get_vod_info", {"vod_id": stream_id})
        self._throttle()
        return payload if isinstance(payload, dict) else {}


__all__ = ["XtreamClient", "XtreamError"]
