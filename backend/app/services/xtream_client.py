from __future__ import annotations

import logging
import random
import time
from collections.abc import Mapping
from typing import Any

import requests

try:  # pragma: no cover - optional dependency during import time
    import cloudscraper  # type: ignore
except Exception:  # pragma: no cover - handled at runtime when falling back
    cloudscraper = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

DEFAULT_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": None,
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

    def _call(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """Call Xtream's ``player_api.php`` handling Cloudflare mitigations."""

        params = params or {}

        base = self.base_url.rstrip("/")
        url = f"{base}/player_api.php"

        headers: dict[str, Any] = {}
        headers.update(DEFAULT_BROWSER_HEADERS)
        if headers.get("Referer") is None:
            headers["Referer"] = base

        session_headers = getattr(self.session, "headers", {}) or {}
        headers.update(session_headers)

        query: dict[str, Any] = {
            "username": self.username,
            "password": self.password,
            "action": action,
            **params,
        }

        https_base = base.replace("http://", "https://") if base.startswith("http://") else base

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            if attempt > 1:
                delay = random.uniform(0.8, 1.5)
                if self.backoff_seconds > 0:
                    delay += self.backoff_seconds * (attempt - 1)
                logger.debug("[Xtream] sleeping %.2fs before retry %d", delay, attempt)
                time.sleep(delay)

            sanitized_query = {
                key: ("***" if "pass" in key.lower() else value)
                for key, value in query.items()
            }

            try:
                logger.debug(
                    "[Xtream] Requesting %s attempt=%d params=%s",
                    url,
                    attempt,
                    sanitized_query,
                )
                session = getattr(self, "session", None)
                if session is not None:
                    resp = session.get(url, params=query, headers=headers, timeout=self.timeout)
                else:
                    resp = requests.get(url, params=query, headers=headers, timeout=self.timeout)

                content_type = resp.headers.get("content-type", "")
                body_head = (resp.text or "")[:512]
                body_head_lower = body_head.lower()
                if (
                    resp.status_code == 403
                    or "text/html" in content_type.lower()
                    or "attention required" in body_head_lower
                    or "cloudflare" in body_head_lower
                ):
                    logger.warning(
                        "[Xtream] Detected HTML/403 from %s (status=%d) — body preview: %.200s",
                        url,
                        resp.status_code,
                        body_head,
                    )

                    if cloudscraper is not None:
                        try:
                            https_url = f"{https_base}/player_api.php"
                            logger.info(
                                "[Xtream] Trying cloudscraper HTTPS fallback to %s (attempt=%d)",
                                https_base,
                                attempt,
                            )
                            cs = cloudscraper.create_scraper()  # type: ignore[call-arg]
                            cs.headers.update(headers)
                            cookies = getattr(session, "cookies", None)
                            if cookies is not None:
                                cs.cookies.update(cookies)  # type: ignore[arg-type]
                            cs_resp = cs.get(https_url, params=query, timeout=self.timeout)
                            cs_content_type = cs_resp.headers.get("content-type", "")
                            cs_body_head = (cs_resp.text or "")[:512]
                            cs_body_head_stripped = cs_body_head.strip()
                            if (
                                cs_resp.status_code == 200
                                and (
                                    "application/json" in cs_content_type.lower()
                                    or cs_body_head_stripped.startswith("{")
                                    or cs_body_head_stripped.startswith("[")
                                )
                            ):
                                logger.info(
                                    "[Xtream] cloudscraper fallback succeeded (HTTPS) on attempt %d",
                                    attempt,
                                )
                                try:
                                    payload = cs_resp.json()
                                except ValueError as exc:
                                    logger.warning(
                                        "[Xtream] cloudscraper fallback returned non-JSON: %.200s",
                                        cs_body_head,
                                    )
                                    last_exc = XtreamError("cloudscraper fallback returned non-JSON")
                                    continue
                                if https_base != base:
                                    self.base_url = https_base
                                return payload

                            logger.warning(
                                "[Xtream] cloudscraper fallback returned status=%d content-type=%s preview=%.200s",
                                cs_resp.status_code,
                                cs_content_type,
                                cs_body_head,
                            )
                            last_exc = XtreamError(
                                f"cloudscraper fallback failed status={cs_resp.status_code}"
                            )
                            continue
                        except Exception as exc:  # pragma: no cover - network failure handling
                            logger.exception("[Xtream] cloudscraper fallback exception: %s", exc)
                            last_exc = exc
                            continue
                    else:
                        logger.warning(
                            "[Xtream] cloudscraper not installed, cannot fallback to bypass Cloudflare",
                        )
                        last_exc = XtreamError("cloudflare blocked and cloudscraper not available")
                        continue

                resp.raise_for_status()

                try:
                    payload = resp.json()
                except ValueError:
                    logger.warning("[Xtream] Response not JSON: preview=%.200s", body_head)
                    last_exc = XtreamError("Response not JSON")
                    continue

                if https_base != base and resp.url.startswith(https_base):
                    self.base_url = https_base
                return payload

            except requests.HTTPError as exc:
                logger.warning("[Xtream] HTTP error on attempt %d: %s", attempt, exc)
                last_exc = exc
            except requests.RequestException as exc:
                logger.warning("[Xtream] Request exception on attempt %d: %s", attempt, exc)
                last_exc = exc

        logger.error("[Xtream] All %d attempts failed for action=%s", self.max_retries, action)
        raise XtreamError(f"Xtream request failed: {last_exc}") from last_exc

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

    def series_streams(self) -> list[dict[str, Any]]:
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

    def series(self) -> list[dict[str, Any]]:
        return self.series_streams()

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


    @classmethod
    def from_settings(
        cls,
        settings: Mapping[str, Any],
        **overrides: Any,
    ) -> "XtreamClient":
        """Create an ``XtreamClient`` from a generic settings mapping.

        The mapping can contain keys from tenant integration settings or
        user-level configuration. Extra keyword arguments are forwarded to the
        constructor, allowing subclasses to receive additional parameters.
        """

        if not isinstance(settings, Mapping):
            raise ValueError("Configurações inválidas para o XtreamClient")

        def _clean(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                trimmed = value.strip()
                return trimmed or None
            return str(value)

        base_url = _clean(
            overrides.pop("base_url", None)
            or settings.get("xtream_base_url")
            or settings.get("api_base_url")
            or settings.get("base_url")
        )
        username = _clean(
            overrides.pop("username", None)
            or settings.get("xtream_username")
            or settings.get("xtream_user")
            or settings.get("username")
        )
        password = overrides.pop("password", None) or settings.get("xtream_password")
        if password is None:
            password = settings.get("xtream_pass")
        if password is None:
            password = settings.get("password")
        if password is not None and not isinstance(password, str):
            password = str(password)
        if isinstance(password, str):
            password = password.strip() or None

        if not base_url or not username or not password:
            raise ValueError("Credenciais Xtream incompletas nas configurações fornecidas")

        def _coerce_int(value: Any) -> int | None:
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        init_kwargs: dict[str, Any] = {
            "base_url": base_url,
            "username": username,
            "password": password,
        }

        raw_options = settings.get("options")
        options = raw_options if isinstance(raw_options, Mapping) else None
        retry_options: Mapping[str, Any] | None = None
        if options is not None:
            raw_retry = options.get("retry")
            if isinstance(raw_retry, Mapping):
                retry_options = raw_retry

        timeout_value = overrides.pop("timeout", None)
        if timeout_value is None:
            timeout_value = settings.get("timeout")
        timeout_coerced = _coerce_int(timeout_value)
        if timeout_coerced is not None:
            init_kwargs["timeout"] = timeout_coerced

        throttle_value = overrides.pop("throttle_ms", None)
        if throttle_value is None and options is not None:
            throttle_value = options.get("throttleMs")
        throttle_coerced = _coerce_int(throttle_value)
        if throttle_coerced is not None:
            init_kwargs["throttle_ms"] = throttle_coerced

        max_parallel_value = overrides.pop("max_parallel", None)
        if max_parallel_value is None and options is not None:
            max_parallel_value = options.get("maxParallel")
        max_parallel_coerced = _coerce_int(max_parallel_value)
        if max_parallel_coerced is not None:
            init_kwargs["max_parallel"] = max_parallel_coerced

        max_retries_value = overrides.pop("max_retries", None)
        if max_retries_value is None and retry_options is not None:
            max_retries_value = retry_options.get("maxAttempts")
        max_retries_coerced = _coerce_int(max_retries_value)
        if max_retries_coerced is not None:
            init_kwargs["max_retries"] = max_retries_coerced

        backoff_value = overrides.pop("backoff_seconds", None)
        if backoff_value is None and retry_options is not None:
            backoff_value = retry_options.get("backoffSeconds")
        backoff_coerced = _coerce_int(backoff_value)
        if backoff_coerced is not None:
            init_kwargs["backoff_seconds"] = backoff_coerced

        init_kwargs.update(overrides)
        return cls(**init_kwargs)


__all__ = ["XtreamClient", "XtreamError"]
