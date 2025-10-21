import type { ApiError } from '../data/adapters/ApiAdapter';

export const DB_SSL_MISCONFIG_CODE = 'DB_SSL_MISCONFIG';
export const DB_ACCESS_DENIED_CODE = 'DB_ACCESS_DENIED';

const DEFAULT_DB_SSL_MISCONFIG_MESSAGE =
  "O servidor MySQL remoto exige conexão SSL, mas não tem suporte ativo. Peça ao responsável pelo banco para corrigir o SSL ou remover o requisito 'REQUIRE SSL'.";

const DEFAULT_DB_ACCESS_DENIED_MESSAGE = [
  'O banco de dados remoto recusou o acesso.',
  'O usuário não tem permissão para conectar a partir deste servidor.',
  'Verifique se o usuário informado possui permissão para conexões externas.',
  'Peça ao responsável pelo banco para executar no MySQL:',
  "GRANT ALL PRIVILEGES ON xui.* TO 'usuario'@'%' IDENTIFIED BY 'sua_senha';",
  'FLUSH PRIVILEGES;',
].join('\n');

type UnknownRecord = Record<string, unknown>;
type ErrorResolver = (message: unknown, record: UnknownRecord) => string | null;

function resolveSslMisconfigMessage(message: unknown): string {
  if (typeof message === 'string' && message.trim().length > 0) {
    return message;
  }
  return DEFAULT_DB_SSL_MISCONFIG_MESSAGE;
}

function resolveAccessDeniedMessage(message: unknown): string {
  if (typeof message === 'string' && message.trim().length > 0) {
    return message;
  }
  return DEFAULT_DB_ACCESS_DENIED_MESSAGE;
}

const ACCESS_DENIED_CODES = new Set([DB_ACCESS_DENIED_CODE]);

const errorResolvers: Record<string, ErrorResolver> = {
  [DB_SSL_MISCONFIG_CODE]: (message) => resolveSslMisconfigMessage(message),
  [DB_ACCESS_DENIED_CODE]: (message) => resolveAccessDeniedMessage(message),
};

function containsErrorCode(value: unknown, targetCodes: Set<string>): boolean {
  if (!value) {
    return false;
  }

  if (Array.isArray(value)) {
    return value.some((item) => containsErrorCode(item, targetCodes));
  }

  if (typeof value === 'object') {
    const record = value as UnknownRecord;
    const code = record['code'];
    if (typeof code === 'string' && targetCodes.has(code)) {
      return true;
    }

    if (containsErrorCode(record['error'], targetCodes)) {
      return true;
    }

    if (containsErrorCode(record['details'], targetCodes)) {
      return true;
    }
  }

  return false;
}

function extractHintForCodes(value: unknown, targetCodes: Set<string>): string | null {
  if (!value) {
    return null;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const hint = extractHintForCodes(item, targetCodes);
      if (hint) {
        return hint;
      }
    }
    return null;
  }

  if (typeof value !== 'object') {
    return null;
  }

  const record = value as UnknownRecord;
  const rawHint = record['hint'];
  const trimmedHint = typeof rawHint === 'string' ? rawHint.trim() : '';

  if (trimmedHint && containsErrorCode(record, targetCodes)) {
    return trimmedHint;
  }

  const nestedError = extractHintForCodes(record['error'], targetCodes);
  if (nestedError) {
    return nestedError;
  }

  const nestedDetails = extractHintForCodes(record['details'], targetCodes);
  if (nestedDetails) {
    return nestedDetails;
  }

  return null;
}

function resolveFromRecord(
  record: UnknownRecord,
  targetCodes?: Set<string>,
): string | null {
  const code = record['code'];
  if (typeof code === 'string' && (!targetCodes || targetCodes.has(code))) {
    const resolver = errorResolvers[code];
    if (resolver) {
      const resolved = resolver(record['message'], record);
      if (resolved) {
        return resolved;
      }
    }
  }

  return null;
}

function extractFromValue(value: unknown, targetCodes?: Set<string>): string | null {
  if (!value) {
    return null;
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      if (item && typeof item === 'object') {
        const nestedResult = extractFromRecord(item as UnknownRecord, targetCodes);
        if (nestedResult) {
          return nestedResult;
        }
      }
    }
    return null;
  }

  if (typeof value === 'object') {
    return extractFromRecord(value as UnknownRecord, targetCodes);
  }

  return null;
}

function extractFromRecord(
  record: UnknownRecord | null | undefined,
  targetCodes?: Set<string>,
): string | null {
  if (!record) {
    return null;
  }

  const resolved = resolveFromRecord(record, targetCodes);
  if (resolved) {
    return resolved;
  }

  const nestedError = extractFromValue(record['error'], targetCodes);
  if (nestedError) {
    return nestedError;
  }

  const nestedDetails = extractFromValue(record['details'], targetCodes);
  if (nestedDetails) {
    return nestedDetails;
  }

  return null;
}

function extractDbErrorMessage(payload: unknown, codes: Set<string>): string | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  return extractFromRecord(payload as UnknownRecord, codes);
}

function extractDbErrorMessageFromApiError(error: ApiError | null | undefined, codes: Set<string>): string | null {
  if (!error) {
    return null;
  }

  const direct = extractFromRecord(error as UnknownRecord, codes);
  if (direct) {
    return direct;
  }

  if (error.details && typeof error.details === 'object') {
    return extractFromRecord(error.details as UnknownRecord, codes);
  }

  return null;
}

export function extractDbSslMisconfigMessage(payload: unknown): string | null {
  return extractDbErrorMessage(payload, new Set([DB_SSL_MISCONFIG_CODE]));
}

export function extractDbSslMisconfigMessageFromApiError(error: ApiError | null | undefined): string | null {
  return extractDbErrorMessageFromApiError(error, new Set([DB_SSL_MISCONFIG_CODE]));
}

export function getDbSslMisconfigFallbackMessage(): string {
  return DEFAULT_DB_SSL_MISCONFIG_MESSAGE;
}

export function extractDbAccessDeniedMessage(payload: unknown): string | null {
  return extractDbErrorMessage(payload, new Set([DB_ACCESS_DENIED_CODE]));
}

export function extractDbAccessDeniedMessageFromApiError(error: ApiError | null | undefined): string | null {
  return extractDbErrorMessageFromApiError(error, new Set([DB_ACCESS_DENIED_CODE]));
}

export function getDbAccessDeniedFallbackMessage(): string {
  return DEFAULT_DB_ACCESS_DENIED_MESSAGE;
}

export function extractDbAccessDeniedHint(payload: unknown): string | null {
  return extractHintForCodes(payload, ACCESS_DENIED_CODES);
}

export function extractDbAccessDeniedHintFromApiError(error: ApiError | null | undefined): string | null {
  if (!error) {
    return null;
  }

  const direct = extractHintForCodes(error as UnknownRecord, ACCESS_DENIED_CODES);
  if (direct) {
    return direct;
  }

  if (error.details && typeof error.details === 'object') {
    return extractHintForCodes(error.details as UnknownRecord, ACCESS_DENIED_CODES);
  }

  return null;
}

export function isAccessDenied(err?: unknown): boolean {
  if (!err) {
    return false;
  }

  return containsErrorCode(err, ACCESS_DENIED_CODES);
}
