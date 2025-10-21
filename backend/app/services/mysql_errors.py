from __future__ import annotations

from typing import Any

SSL_MISCONFIG_ERROR_CODE = "DB_SSL_MISCONFIG"
SSL_MISCONFIG_ERROR_MESSAGE = (
    "O servidor MySQL remoto exige conexão SSL, mas não tem suporte ativo. Peça ao "
    "responsável pelo banco para corrigir o SSL ou remover o requisito 'REQUIRE SSL'."
)

ACCESS_DENIED = "DB_ACCESS_DENIED"
ACCESS_DENIED_ERROR_MESSAGE = (
    "O banco de dados remoto recusou o acesso. O usuário não tem permissão para conectar a "
    "partir deste servidor. Peça ao responsável pelo banco para executar: GRANT ALL PRIVILEGES "
    "ON xui.* TO 'usuario'@'%' IDENTIFIED BY 'senha';"
)

_SSL_ERROR_CODES = {2026}
_SSL_ERROR_PATTERNS = (
    "ssl is required",
    "requires ssl",
    "ssl connection error",
)

_ACCESS_DENIED_CODES = {1045}
_ACCESS_DENIED_PATTERNS = ("access denied for user",)


class MysqlSslMisconfigurationError(RuntimeError):
    """Exceção que representa um requisito de SSL inconsistente no servidor."""

    def __init__(self, *, host: str | None = None, user: str | None = None) -> None:
        self.host = host or ""
        self.user = user or ""
        super().__init__(SSL_MISCONFIG_ERROR_MESSAGE)


class MysqlAccessDeniedError(RuntimeError):
    """Exceção que representa rejeição de acesso pelo servidor MySQL remoto."""

    def __init__(
        self,
        *,
        host: str | None = None,
        user: str | None = None,
        database: str | None = None,
    ) -> None:
        self.host = host or ""
        self.user = user or ""
        self.database = database or ""
        message = _build_access_denied_message(user=self.user, database=self.database)
        super().__init__(message)


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


def _matches_access_denied_message(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(pattern in lowered for pattern in _ACCESS_DENIED_PATTERNS)


def _matches_access_denied_args(args: tuple[Any, ...]) -> bool:
    for item in args:
        if isinstance(item, int) and item in _ACCESS_DENIED_CODES:
            return True
        if isinstance(item, (tuple, list)):
            if _matches_access_denied_args(tuple(item)):
                return True
        if isinstance(item, str) and _matches_access_denied_message(item):
            return True
    return False


def is_access_denied_error(exc: BaseException | None) -> bool:
    """Inspeciona a cadeia de exceções procurando erros de acesso negado."""

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
        if isinstance(args, tuple) and _matches_access_denied_args(args):
            return True

        message = str(current)
        if _matches_access_denied_message(message):
            return True

        for attr in ("orig", "__cause__", "__context__"):
            nested = getattr(current, attr, None)
            if nested is not None and nested is not current:
                stack.append(nested)  # type: ignore[arg-type]

    return False


def _build_access_denied_message(*, user: str | None, database: str | None) -> str:
    normalized_user = (user or "usuario").strip() or "usuario"
    normalized_database = (database or "xui").strip() or "xui"
    return (
        "O banco de dados remoto recusou o acesso.\n"
        "O usuário não tem permissão para conectar a partir deste servidor.\n"
        f"Verifique se o usuário {normalized_user} possui permissão para conexões externas.\n"
        "Peça ao responsável pelo banco para executar no MySQL:\n"
        f"GRANT ALL PRIVILEGES ON {normalized_database}.* TO '{normalized_user}'@'%' IDENTIFIED BY 'sua_senha';\n"
        "FLUSH PRIVILEGES;"
    )


def build_access_denied_response(
    *, user: str | None = None, database: str | None = None
) -> dict[str, Any]:
    message = _build_access_denied_message(user=user, database=database)
    return {
        "success": False,
        "error": {
            "code": ACCESS_DENIED,
            "message": message,
        },
    }
