import type { ApiError } from '../data/adapters/ApiAdapter';

export const DB_SSL_MISCONFIG_CODE = 'DB_SSL_MISCONFIG';

const DEFAULT_DB_SSL_MISCONFIG_MESSAGE =
  "O servidor MySQL remoto exige conexão SSL, mas não tem suporte ativo. Peça ao responsável pelo banco para corrigir o SSL ou remover o requisito 'REQUIRE SSL'.";

type UnknownRecord = Record<string, unknown>;

function resolveSslMisconfigMessage(message: unknown): string {
  if (typeof message === 'string' && message.trim().length > 0) {
    return message;
  }
  return DEFAULT_DB_SSL_MISCONFIG_MESSAGE;
}

function extractFromRecord(record: UnknownRecord | null | undefined): string | null {
  if (!record) {
    return null;
  }

  const code = record['code'];
  const message = record['message'];

  if (code === DB_SSL_MISCONFIG_CODE) {
    return resolveSslMisconfigMessage(message);
  }

  const nested = record['error'];
  if (nested && typeof nested === 'object') {
    const nestedRecord = nested as UnknownRecord;
    const nestedCode = nestedRecord['code'];
    if (nestedCode === DB_SSL_MISCONFIG_CODE) {
      return resolveSslMisconfigMessage(nestedRecord['message']);
    }
  }

  return null;
}

export function extractDbSslMisconfigMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  return extractFromRecord(payload as UnknownRecord);
}

export function extractDbSslMisconfigMessageFromApiError(error: ApiError | null | undefined): string | null {
  if (!error) {
    return null;
  }

  const direct = extractFromRecord(error as UnknownRecord);
  if (direct) {
    return direct;
  }

  if (error.details && typeof error.details === 'object') {
    return extractFromRecord(error.details as UnknownRecord);
  }

  return null;
}

export function getDbSslMisconfigFallbackMessage(): string {
  return DEFAULT_DB_SSL_MISCONFIG_MESSAGE;
}
