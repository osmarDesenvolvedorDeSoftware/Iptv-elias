from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.engine import make_url

from . import create_app
from .services import settings as settings_service
from .services.xtream_client import XtreamClient, XtreamError

LOG_FILE = Path("/app/logs/debug_xtream.log")


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - usado apenas em CLI
        message = super().format(record)
        color = self.COLORS.get(record.levelno)
        if color:
            return f"{color}{message}{self.RESET}"
        return message


@dataclass(slots=True)
class RequestLogEntry:
    timestamp: str
    action: str | None
    method: str
    url: str
    params: dict[str, Any]
    headers: dict[str, Any]
    status_code: int | None
    reason: str | None
    content_type: str | None
    content_length: int | None
    response_headers: dict[str, Any] | None
    preview: str
    duration_seconds: float
    response_size_bytes: int | None
    is_html: bool
    exception: Exception | None


def _mask_secret(secret: Any) -> str:
    if secret is None:
        return "<não informado>"
    if isinstance(secret, str) and not secret.strip():
        return "<não informado>"
    return "***"


def _mask_mysql_uri(uri: str | None) -> str:
    if not uri:
        return "<não configurado>"
    try:
        return make_url(uri).render_as_string(hide_password=True)
    except Exception:  # pragma: no cover - defensivo contra URIs inválidas
        return uri


def _mask_params(params: Mapping[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in params.items():
        key_str = str(key)
        if key_str.lower() in {"password", "pass", "pwd"}:
            masked[key_str] = _mask_secret(value)
        else:
            masked[key_str] = value
    return masked


def _mask_headers(headers: Mapping[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in headers.items():
        lower_key = str(key).lower()
        if lower_key in {"authorization", "cookie", "x-authorization"}:
            masked[key] = _mask_secret(value)
        else:
            masked[key] = value
    return masked


class RequestLogCollector:
    def __init__(self, logger: logging.LoggerAdapter, tenant_id: str, user_id: int) -> None:
        self.logger = logger
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.total = 0
        self.success = 0
        self.html = 0
        self.forbidden = 0
        self.errors = 0

    def log_request(self, entry: RequestLogEntry) -> None:
        self.total += 1
        level = logging.INFO
        if entry.exception is not None:
            level = logging.ERROR
            self.errors += 1
        elif entry.status_code == 403 or entry.is_html:
            level = logging.WARNING

        if entry.status_code == 403:
            self.forbidden += 1
        if entry.is_html:
            self.html += 1

        if level == logging.INFO and entry.exception is None and not entry.is_html and entry.status_code != 403:
            self.success += 1

        payload = {
            "timestamp": entry.timestamp,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "endpoint": entry.action,
            "http_method": entry.method,
            "url": entry.url,
            "status_code": entry.status_code,
            "reason": entry.reason,
            "duration_ms": round(entry.duration_seconds * 1000, 2),
            "content_type": entry.content_type,
            "content_length_header": entry.content_length,
            "response_size_bytes": entry.response_size_bytes,
            "request_headers": entry.headers,
            "request_params": entry.params,
            "response_headers": entry.response_headers,
            "response_preview": entry.preview,
            "is_html": entry.is_html,
        }

        if entry.exception is not None:
            payload["exception_type"] = type(entry.exception).__name__
            payload["exception_message"] = str(entry.exception)

        alert_text: str | None = None
        if entry.status_code == 403 or entry.is_html:
            alert_text = "⚠️ Possível bloqueio Cloudflare — resposta não JSON detectada"
            payload["cloudflare_alert"] = True

        log_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if alert_text:
            self.logger.log(level, "%s\n%s", alert_text, log_text)
        else:
            self.logger.log(level, log_text)

    def summarize(self) -> dict[str, int]:
        return {
            "total": self.total,
            "success": self.success,
            "html": self.html,
            "forbidden": self.forbidden,
            "errors": self.errors,
        }

    def log_summary(self) -> dict[str, int]:
        summary = self.summarize()
        message = (
            "Resumo final — total={total} | sucesso={success} | html={html} | "
            "status_403={forbidden} | erros={errors}"
        ).format(**summary)

        if summary["errors"] > 0:
            level = logging.ERROR
        elif summary["html"] > 0 or summary["forbidden"] > 0:
            level = logging.WARNING
        else:
            level = logging.INFO

        self.logger.log(level, message)
        return summary


class DebugXtreamClient(XtreamClient):
    def __init__(self, *args: Any, observer: RequestLogCollector | None = None, **kwargs: Any) -> None:
        self._observer = observer
        super().__init__(*args, **kwargs)

    def _perform_request(self, url: str, *, params: dict[str, Any], headers: dict[str, str]) -> requests.Response:
        timestamp = datetime.now(timezone.utc).isoformat()
        masked_headers = _mask_headers(headers)
        masked_params = _mask_params(params)
        start_time = time.monotonic()
        response: requests.Response | None = None
        error: Exception | None = None

        try:
            response = super()._perform_request(url, params=params, headers=headers)
            return response
        except requests.HTTPError as exc:
            error = exc
            response = exc.response
            raise
        except requests.RequestException as exc:
            error = exc
            raise
        finally:
            if self._observer is not None:
                duration = time.monotonic() - start_time
                status_code = response.status_code if response is not None else None
                reason = response.reason if response is not None else None
                content_type = response.headers.get("Content-Type") if response is not None else None
                content_length: int | None = None
                response_headers: dict[str, Any] | None = None
                preview = ""
                response_size: int | None = None
                is_html = False

                if response is not None:
                    header_length = response.headers.get("Content-Length")
                    if header_length is not None:
                        try:
                            content_length = int(header_length)
                        except (TypeError, ValueError):
                            content_length = None
                    response_headers = dict(response.headers.items())
                    try:
                        body_text = response.text or ""
                    except Exception:  # pragma: no cover - falhas raras de decodificação
                        body_text = ""
                    preview = body_text[:500]
                    response_content = response.content or b""
                    response_size = len(response_content)
                    if not preview and response_content:
                        preview = response_content[:500].decode("utf-8", errors="replace")
                    if preview:
                        lowered = preview.lower()
                        if "<html" in lowered or "<!doctype" in lowered:
                            is_html = True
                    if not is_html and content_type:
                        if "html" in content_type.lower():
                            is_html = True

                action = params.get("action")
                entry = RequestLogEntry(
                    timestamp=timestamp,
                    action=str(action) if action is not None else None,
                    method="GET",
                    url=url,
                    params=masked_params,
                    headers=masked_headers,
                    status_code=status_code,
                    reason=reason,
                    content_type=content_type,
                    content_length=content_length,
                    response_headers=response_headers,
                    preview=preview,
                    duration_seconds=duration,
                    response_size_bytes=response_size,
                    is_html=is_html,
                    exception=error,
                )
                self._observer.log_request(entry)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug da API Xtream para sincronização")
    parser.add_argument("--tenant", dest="tenant_id", required=True, help="Identificador do tenant")
    parser.add_argument("--user", dest="user_id", required=True, type=int, help="ID do usuário associado")
    return parser.parse_args(argv)


def setup_logger(tenant_id: str, user_id: int) -> logging.LoggerAdapter:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("debug_xtream")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s [tenant=%(tenant)s user=%(user)s] %(levelname)s %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColorFormatter(
        "%(asctime)s [tenant=%(tenant)s user=%(user)s] %(levelname)s %(message)s",
        "%H:%M:%S",
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logging.LoggerAdapter(logger, {"tenant": tenant_id, "user": user_id})


def _describe_xtream(client: XtreamClient) -> str:
    payload = {
        "base_url": client.base_url,
        "username": client.username,
        "password": _mask_secret(client.password),
        "timeout": getattr(client, "timeout", None),
        "throttle_ms": getattr(client, "throttle_ms", None),
        "max_retries": getattr(client, "max_retries", None),
        "backoff_seconds": getattr(client, "backoff_seconds", None),
        "max_parallel": getattr(client, "max_parallel", None),
    }
    return json.dumps(payload, ensure_ascii=False)


def run_debug(tenant_id: str, user_id: int, logger: logging.LoggerAdapter) -> int:
    app = create_app()
    collector: RequestLogCollector | None = None
    exit_code = 0

    with app.app_context():
        logger.info("Iniciando captura de debug para o tenant %s e usuário %s", tenant_id, user_id)

        settings_payload = settings_service.get_settings_with_secrets(tenant_id, user_id)
        mysql_uri = settings_service.build_mysql_uri(settings_payload)
        logger.info("MySQL configurado: %s", _mask_mysql_uri(mysql_uri))

        collector = RequestLogCollector(logger, tenant_id, user_id)

        try:
            client = DebugXtreamClient.from_settings(settings_payload, observer=collector)
        except ValueError as exc:
            logger.error("Não foi possível inicializar o XtreamClient: %s", exc)
            exit_code = 1
        else:
            logger.info("Configuração Xtream carregada: %s", _describe_xtream(client))

            actions = [
                ("get_vod_streams", client.vod_streams),
                ("get_series_streams", client.series_streams),
            ]

            for action_name, callable_action in actions:
                logger.info("Executando %s", action_name)
                started = time.monotonic()
                try:
                    result = callable_action()
                except XtreamError as exc:
                    exit_code = 1
                    logger.error("XtreamError em %s: %s", action_name, exc)
                except requests.Timeout as exc:
                    exit_code = 1
                    logger.error("Timeout em %s: %s", action_name, exc)
                except requests.RequestException as exc:
                    exit_code = 1
                    logger.error("Erro de rede em %s: %s", action_name, exc)
                except Exception as exc:  # pragma: no cover - segurança extra
                    exit_code = 1
                    logger.error("Erro inesperado em %s: %s", action_name, exc, exc_info=True)
                else:
                    duration = time.monotonic() - started
                    item_count = len(result) if isinstance(result, list) else None
                    logger.info(
                        "%s concluído em %.2fs — itens retornados: %s",
                        action_name,
                        duration,
                        item_count if item_count is not None else "desconhecido",
                    )
        finally:
            if collector is not None:
                summary = collector.log_summary()
                if exit_code == 0 and summary.get("errors"):
                    exit_code = 1

    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logger = setup_logger(args.tenant_id, args.user_id)

    try:
        return run_debug(args.tenant_id, args.user_id, logger)
    except Exception as exc:  # pragma: no cover - garante logging de falhas inesperadas
        logger.error("Falha inesperada no debug: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":  # pragma: no cover - execução manual
    sys.exit(main())
