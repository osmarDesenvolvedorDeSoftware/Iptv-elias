from __future__ import annotations

from typing import Any

SSL_MISCONFIG_ERROR_CODE = "DB_SSL_MISCONFIG"
SSL_MISCONFIG_ERROR_MESSAGE = (
    "O servidor MySQL remoto exige conexão SSL, mas não tem suporte ativo. Peça ao "
    "responsável pelo banco para corrigir o SSL ou remover o requisito 'REQUIRE SSL'."
)

_SSL_ERROR_CODES = {2026}
_SSL_ERROR_PATTERNS = (
    "ssl is required",
    "requires ssl",
    "ssl connection error",
)


class MysqlSslMisconfigurationError(RuntimeError):
    """Exceção que representa um requisito de SSL inconsistente no servidor."""

    def __init__(self, *, host: str | None = None, user: str | None = None) -> None:
        self.host = host or ""
        self.user = user or ""
        super().__init__(SSL_MISCONFIG_ERROR_MESSAGE)


def _matches_message(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(pattern in lowered for pattern in _SSL_ERROR_PATTERNS)


def _matches_args(args: tuple[Any, ...]) -> bool:
    for item in args:
        if isinstance(item, int) and item in _SSL_ERROR_CODES:
            return True
        if isinstance(item, (tuple, list)):
            if _matches_args(tuple(item)):
                return True
        if isinstance(item, str) and _matches_message(item):
            return True
    return False


def is_ssl_misconfiguration_error(exc: BaseException | None) -> bool:
    """Inspeciona a cadeia de exceções procurando indícios de erro de SSL."""

    seen: set[int] = set()
    stack: list[BaseException | None] = [exc]
    while stack:
        current = stack.pop()
        if current is None:
            continue
        ident = id(current)
        if ident in seen:
            continue
        seen.add(ident)

        args = getattr(current, "args", ())
        if isinstance(args, tuple) and _matches_args(args):
            return True

        message = str(current)
        if _matches_message(message):
            return True

        for attr in ("orig", "__cause__", "__context__"):
            nested = getattr(current, attr, None)
            if nested is not None and nested is not current:
                stack.append(nested)  # type: ignore[arg-type]

    return False


def build_ssl_misconfiguration_response() -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": SSL_MISCONFIG_ERROR_CODE,
            "message": SSL_MISCONFIG_ERROR_MESSAGE,
        },
    }
