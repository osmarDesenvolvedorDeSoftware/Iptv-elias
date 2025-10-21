from __future__ import annotations

import logging
import time
from typing import Any

import cloudscraper
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
        self.session = session or cloudscraper.create_scraper()
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

    @staticmethod
    def _is_html_body(body: str | None) -> bool:
        if not body:
            return False
        return "<html" in body.lower()

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
        last_error: Exception | None = None
        last_body_preview: str = ""
        current_url = url

        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                time.sleep(1)
            response_obj: requests.Response | None = None
            try:
                response_obj = self._perform_request(current_url, params=query, headers=headers)
                try:
                    payload = response_obj.json()
                except ValueError as json_error:
                    body_preview = (response_obj.text or "")[:400]
                    last_body_preview = body_preview if body_preview else "<resposta vazia>"
                    last_error = json_error
                    if self._is_html_body(body_preview):
                        logger.warning(
                            "⚠️ Xtream bloqueado pelo Cloudflare — resposta HTML interceptada."
                        )
                        if https_url and current_url != https_url:
                            current_url = https_url
                            continue
                    continue
                if https_base_url and https_url and current_url == https_url:
                    self.base_url = https_base_url
                return payload
            except requests.HTTPError as exc:
                last_error = exc
                response_obj = exc.response
                status_code = response_obj.status_code if response_obj is not None else None
                body_preview = ""
                if response_obj is not None:
                    body_preview = (response_obj.text or "")[:400]
                    last_body_preview = body_preview if body_preview else "<resposta vazia>"
                is_html = self._is_html_body(body_preview)
                is_403 = status_code == 403
                if is_403 or is_html:
                    logger.warning(
                        "⚠️ Xtream bloqueado pelo Cloudflare — resposta HTML interceptada."
                    )
                if is_403 and https_url and current_url != https_url:
                    logger.info(
                        "Xtream request received HTTP 403 for %s, retrying via HTTPS: %s",
                        current_url,
                        https_url,
                    )
                    current_url = https_url
                    continue
                if is_html and https_url and current_url != https_url:
                    current_url = https_url
                    continue
            except requests.RequestException as exc:
                last_error = exc

            body_preview = ""
            if response_obj is not None:
                try:
                    body_preview = (response_obj.text or "")[:400]
                except Exception:  # pragma: no cover - defensive
                    body_preview = ""
            if response_obj is not None:
                last_body_preview = body_preview if body_preview else "<resposta vazia>"

            if attempt < self.max_retries:
                if self.backoff_seconds > 0:
                    time.sleep(self.backoff_seconds * attempt)

        raise XtreamError(
            (
                f"Xtream API falhou após {self.max_retries} tentativas: {last_error}. "
                f"Última resposta: {last_body_preview}"
            )
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
