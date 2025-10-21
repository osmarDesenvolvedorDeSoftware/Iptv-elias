import { get, post, put } from '../adapters/ApiAdapter';
import { AccountConfigPayload, ParsedM3UResponse, UserConfigData } from '../types';

type RawUserSettings =
  | (UserConfigData & Record<string, unknown>)
  | ({ settings?: UserConfigData & Record<string, unknown> } & Record<string, unknown>)
  | null;

function toOptionalString(value: unknown): string | null {
  if (typeof value === 'string') {
    return value;
  }
  if (value === undefined || value === null) {
    return null;
  }
  return String(value);
}

function toOptionalNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toOptionalBoolean(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (!normalized) {
      return fallback;
    }
    return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'sim';
  }
  return fallback;
}

function normalizeUserSettings(raw: RawUserSettings): UserConfigData | null {
  if (!raw) {
    return null;
  }

  const payload: Record<string, unknown> =
    typeof raw === 'object' && raw !== null && 'settings' in raw
      ? ((raw as { settings?: Record<string, unknown> }).settings ?? {})
      : ((raw as Record<string, unknown>) ?? {});

  if (Object.keys(payload).length === 0) {
    return null;
  }

  const domain = toOptionalString(payload['domain']);
  const username = toOptionalString(
    payload['username'] !== undefined ? payload['username'] : payload['api_username'],
  );
  const password = toOptionalString(payload['password']);
  const linkM3u = toOptionalString(
    payload['linkM3u'] ??
      payload['link_m3u'] ??
      payload['link'] ??
      payload['m3u_link'] ??
      payload['m3uLink'],
  );
  const lastSync = toOptionalString(payload['lastSync'] ?? payload['last_sync']);
  const xuiDbUri = toOptionalString(payload['xuiDbUri'] ?? payload['xui_db_uri']);
  const activeValue = payload['active'];
  const hasPasswordValue = payload['hasPassword'];
  const connectionReadyValue = payload['connectionReady'];
  const dbHost = toOptionalString(payload['db_host'] ?? payload['dbHost']);
  const dbPort = toOptionalNumber(payload['db_port'] ?? payload['dbPort']);
  const dbUser = toOptionalString(payload['db_user'] ?? payload['dbUser']);
  const dbName = toOptionalString(payload['db_name'] ?? payload['dbName']);
  const dbPasswordMaskedRaw =
    payload['db_password_masked'] ?? payload['dbPasswordMasked'] ?? payload['db_pass_masked'];
  const dbStatusRaw =
    payload['db_connection_status'] ?? payload['dbConnectionStatus'] ?? payload['last_test_status'];
  const dbMessage = toOptionalString(
    payload['db_connection_message'] ?? payload['dbConnectionMessage'] ?? payload['last_test_message'],
  );
  const dbTestedAt = toOptionalString(payload['db_tested_at'] ?? payload['dbTestedAt'] ?? payload['last_test_at']);
  const dbConnectionReadyValue =
    payload['dbConnectionReady'] ?? payload['db_connection_ready'] ?? (dbStatusRaw === 'success');

  const dbStatusText = toOptionalString(dbStatusRaw);
  const dbConnectionStatus =
    dbStatusText && (dbStatusText === 'success' || dbStatusText === 'error')
      ? (dbStatusText as 'success' | 'error')
      : null;
  const dbPasswordMasked =
    typeof dbPasswordMaskedRaw === 'boolean'
      ? dbPasswordMaskedRaw
      : dbPasswordMaskedRaw === '1' || dbPasswordMaskedRaw === 'true';

  const normalized: UserConfigData = {
    domain: domain ?? null,
    port: toOptionalNumber(payload['port']),
    username: username ?? null,
    password: password ?? null,
    linkM3u: linkM3u ?? null,
    link: linkM3u ?? null,
    active: toOptionalBoolean(activeValue, false),
    lastSync: lastSync ?? null,
    hasPassword: typeof hasPasswordValue === 'boolean' ? (hasPasswordValue as boolean) : Boolean(password),
    connectionReady: typeof connectionReadyValue === 'boolean' ? (connectionReadyValue as boolean) : undefined,
    xuiDbUri: xuiDbUri ?? null,
    dbHost: dbHost ?? null,
    dbPort,
    dbUser: dbUser ?? null,
    dbName: dbName ?? null,
    dbPasswordMasked,
    dbConnectionStatus,
    dbConnectionMessage: dbMessage ?? null,
    dbTestedAt: dbTestedAt ?? null,
    dbConnectionReady:
      typeof dbConnectionReadyValue === 'boolean' ? (dbConnectionReadyValue as boolean) : undefined,
  };

  return normalized;
}

export async function fetchConfig(): Promise<UserConfigData | null> {
  const response = await get<RawUserSettings>('/api/settings');
  return normalizeUserSettings(response);
}

export async function parseM3U(link: string): Promise<ParsedM3UResponse> {
  const response = await post<ParsedM3UResponse>('/account/parse_m3u', { link });
  return response;
}

export async function saveAccountConfig(config: AccountConfigPayload): Promise<UserConfigData> {
  const response = await put<UserConfigData>('/account/config', config);
  return response;
}

export interface SaveUserSettingsPayload {
  link_m3u?: string | null;
  domain?: string | null;
  port?: number | null;
  username?: string | null;
  password?: string | null;
  active?: boolean;
  db_host?: string | null;
  db_port?: number | null;
  db_user?: string | null;
  db_password?: string | null;
  db_name?: string | null;
}

export async function saveUserSettings(payload: SaveUserSettingsPayload): Promise<UserConfigData | null> {
  const response = await put<RawUserSettings>('/api/settings', payload);
  return normalizeUserSettings(response);
}

export interface TestDatabaseResponse {
  success: boolean;
  message: string;
  status?: 'success' | 'error';
  testedAt?: string | null;
}

export async function testDatabaseConnection(
  payload: Partial<SaveUserSettingsPayload>,
): Promise<TestDatabaseResponse> {
  const response = await post<TestDatabaseResponse>('/api/settings/test-db', payload);
  return response;
}
