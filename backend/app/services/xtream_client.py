from __future__ import annotations

import time
from typing import Any

import requests


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

    def _call(self, action: str, params: dict[str, Any] | None = None) -> Any:
        query = {
            "username": self.username,
            "password": self.password,
            "action": action,
        }
        if params:
            query.update(params)
        url = f"{self.base_url}/player_api.php"

        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.session.get(url, params=query, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise XtreamError(f"Xtream API falhou após {attempt} tentativas: {exc}") from exc
                time.sleep(self.backoff_seconds * attempt)

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
