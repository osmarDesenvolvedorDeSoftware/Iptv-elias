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
}

export async function saveUserSettings(payload: SaveUserSettingsPayload): Promise<UserConfigData | null> {
  const response = await put<RawUserSettings>('/api/settings', payload);
  return normalizeUserSettings(response);
}
