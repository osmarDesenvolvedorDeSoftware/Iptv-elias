import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import {
  ConfigResetResponse,
  ConfigSaveResponse,
  ConfigSchema,
  ConfigTestResponse,
  GeneralSettings,
  SaveConfigPayload,
} from '../types';

interface RawSettings {
  db_host?: string;
  db_port?: number;
  db_user?: string;
  db_pass_masked?: boolean;
  db_name?: string;
  api_base_url?: string;
  m3u_link?: string;
  tmdb_key_masked?: boolean;
  xtream_user?: string;
  xtream_pass_masked?: boolean;
  use_xtream_api?: boolean;
  bouquet_normal?: number | null;
  bouquet_adulto?: number | null;
  ignored_prefixes?: unknown;
  last_test_status?: 'success' | 'error' | null;
  last_test_message?: string | null;
  last_test_at?: string | null;
}

const mockSettings: GeneralSettings = {
  dbHost: 'localhost',
  dbPort: 3306,
  dbUser: 'root',
  dbName: 'xui',
  apiBaseUrl: 'http://localhost:5000',
  m3uLink: 'http://example.com/list.m3u',
  tmdbKeyMasked: false,
  xtreamUser: 'demo',
  useXtreamApi: true,
  bouquetNormal: null,
  bouquetAdulto: null,
  ignoredPrefixes: ['Filmes'],
  dbPassMasked: false,
  xtreamPassMasked: false,
  lastTestStatus: null,
  lastTestMessage: null,
  lastTestAt: null,
};

const mockSchema: ConfigSchema = {
  defaults: {},
  fields: {
    db_host: { type: 'string', label: 'Host do MySQL', required: true },
    db_port: { type: 'number', label: 'Porta', required: true, min: 1, max: 65535 },
    db_user: { type: 'string', label: 'Usuário', required: true },
    db_pass: { type: 'password', label: 'Senha', required: false },
    db_name: { type: 'string', label: 'Banco', required: true },
    api_base_url: { type: 'url', label: 'URL da API', required: false },
    m3u_link: { type: 'url', label: 'Lista M3U', required: false },
    tmdb_key: { type: 'password', label: 'Chave TMDb', required: false },
    xtream_user: { type: 'string', label: 'Usuário Xtream', required: false },
    xtream_pass: { type: 'password', label: 'Senha Xtream', required: false },
    use_xtream_api: { type: 'boolean', label: 'Usar API Xtream', required: true },
    bouquet_normal: { type: 'number', label: 'Bouquet Normal', required: false },
    bouquet_adulto: { type: 'number', label: 'Bouquet Adulto', required: false },
    ignored_prefixes: { type: 'list', label: 'Prefixos ignorados', required: false },
  },
};

function normalizeSettings(raw: RawSettings): GeneralSettings {
  const ignored = Array.isArray(raw.ignored_prefixes)
    ? raw.ignored_prefixes.filter((item): item is string => typeof item === 'string')
    : [];

  return {
    dbHost: raw.db_host ?? '',
    dbPort: Number(raw.db_port ?? 3306),
    dbUser: raw.db_user ?? '',
    dbName: raw.db_name ?? '',
    apiBaseUrl: raw.api_base_url ?? '',
    m3uLink: raw.m3u_link ?? '',
    tmdbKeyMasked: Boolean(raw.tmdb_key_masked),
    xtreamUser: raw.xtream_user ?? '',
    useXtreamApi: raw.use_xtream_api ?? true,
    bouquetNormal: raw.bouquet_normal ?? null,
    bouquetAdulto: raw.bouquet_adulto ?? null,
    ignoredPrefixes: ignored,
    dbPassMasked: Boolean(raw.db_pass_masked),
    xtreamPassMasked: Boolean(raw.xtream_pass_masked),
    lastTestStatus: raw.last_test_status ?? null,
    lastTestMessage: raw.last_test_message ?? null,
    lastTestAt: raw.last_test_at ?? null,
  };
}

function serializeConfigPayload(payload: Partial<SaveConfigPayload>): Record<string, unknown> {
  const body: Record<string, unknown> = {};

  if (payload.dbHost !== undefined) body.db_host = payload.dbHost;
  if (payload.dbPort !== undefined) body.db_port = payload.dbPort;
  if (payload.dbUser !== undefined) body.db_user = payload.dbUser;
  if (payload.dbName !== undefined) body.db_name = payload.dbName;
  if (payload.apiBaseUrl !== undefined) body.api_base_url = payload.apiBaseUrl;
  if (payload.m3uLink !== undefined) body.m3u_link = payload.m3uLink;
  if (payload.tmdbKey !== undefined) body.tmdb_key = payload.tmdbKey;
  if (payload.xtreamUser !== undefined) body.xtream_user = payload.xtreamUser;
  if (payload.useXtreamApi !== undefined) body.use_xtream_api = payload.useXtreamApi;
  if (payload.bouquetNormal !== undefined) body.bouquet_normal = payload.bouquetNormal;
  if (payload.bouquetAdulto !== undefined) body.bouquet_adulto = payload.bouquetAdulto;
  if (payload.ignoredPrefixes !== undefined) body.ignored_prefixes = payload.ignoredPrefixes;
  if (payload.dbPass !== undefined) body.db_pass = payload.dbPass;
  if (payload.xtreamPass !== undefined) body.xtream_pass = payload.xtreamPass;

  return body;
}

export async function getConfig(): Promise<GeneralSettings> {
  if (isMockEnabled) {
    return MockAdapter.fetch<GeneralSettings>('config.get.json').catch(() => mockSettings);
  }

  const raw = await get<RawSettings>('/config/me');
  return normalizeSettings(raw);
}

export async function getConfigSchema(): Promise<ConfigSchema> {
  if (isMockEnabled) {
    return mockSchema;
  }

  return get<ConfigSchema>('/config/schema');
}

export async function saveConfig(payload: SaveConfigPayload): Promise<GeneralSettings> {
  if (isMockEnabled) {
    return MockAdapter.fetch<GeneralSettings>('config.save.json', { minDelayMs: 400, maxDelayMs: 800 }).catch(
      () => ({ ...mockSettings, ...payload }),
    );
  }

  const body = serializeConfigPayload(payload);
  const response = await post<ConfigSaveResponse>('/config/me', body);
  return normalizeSettings(response.settings);
}

export async function resetConfig(): Promise<GeneralSettings> {
  if (isMockEnabled) {
    return mockSettings;
  }

  const response = await post<ConfigResetResponse>('/config/me/reset', {});
  return normalizeSettings(response.settings);
}

export async function testConfig(payload: Partial<SaveConfigPayload>): Promise<ConfigTestResponse> {
  if (isMockEnabled) {
    return { success: true, message: 'Conexão simulada com sucesso.', status: 'success', testedAt: new Date().toISOString() };
  }

  const body = serializeConfigPayload(payload);
  return post<ConfigTestResponse>('/config/me/test', body);
}
