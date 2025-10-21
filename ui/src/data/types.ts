export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  tenantId: string;
  tenantName?: string;
  lastLogin?: string | null;
  isActive?: boolean;
}

export interface AuthLoginResponse {
  token: string;
  refreshToken: string;
  expiresInSec: number;
  user: User;
}

export interface AuthRefreshResponse {
  token: string;
  expiresInSec: number;
}

export interface UserConfigData {
  domain: string | null;
  port: number | null;
  username: string | null;
  active: boolean;
  lastSync?: string | null;
  hasPassword?: boolean;
  connectionReady?: boolean;
  xuiDbUri?: string | null;
}

export interface AccountConfigPayload {
  link?: string | null;
  linkM3u?: string | null;
  link_m3u?: string | null;
  domain?: string | null;
  port?: number | null;
  username?: string | null;
  password?: string | null;
  active?: boolean;
  xuiDbUri?: string | null;
}

export interface ParsedM3UResponse {
  domain: string;
  port: number;
  username: string;
  password: string;
  xuiDbUri?: string | null;
}

export interface AdminStats {
  totalUsers: number;
  activeUsers: number;
  totalJobs: number;
  failedJobs: number;
  lastSync?: string | null;
}

export interface AdminRecentError {
  id: number;
  type: string;
  tenantId: string;
  userId: number;
  finishedAt?: string | null;
  error?: string | null;
}

export interface AdminUser extends User {
  createdAt?: string | null;
  config?: UserConfigData | null;
}

export type ImportType = 'filmes' | 'series';

export type ImportJobStatus = 'queued' | 'running' | 'finished' | 'failed';

export interface ImportJobHistoryItem {
  id: number;
  startedAt: string;
  finishedAt?: string;
  status: ImportJobStatus;
  inserted?: number;
  updated?: number;
  ignored?: number;
  errors?: number;
  durationSec?: number;
  progress?: number;
  etaSec?: number;
  trigger: string;
  user: string;
  type?: ImportType;
  sourceTag?: string;
  sourceTagFilmes?: string;
  error?: string | null;
  normalization?: NormalizationInfo;
}

export interface ImportListResponse {
  items: ImportJobHistoryItem[];
  page: number;
  pageSize: number;
  total: number;
}

export interface ImportRunResponse {
  jobId: number;
  status: ImportJobStatus;
}

export interface JobStatusResponse {
  id: number;
  status: ImportJobStatus | 'cancelled';
  progress?: number;
  etaSec?: number;
}

export interface NormalizationSuccess {
  status: 'success';
  logId: number;
  createdAt: string;
  streams: {
    total?: number;
    updated?: number;
    moviesTagged?: number;
  };
  series: {
    total?: number;
    tagged?: number;
    episodesAnalyzed?: number;
  };
}

export interface NormalizationFailure {
  status: 'failed';
  logId: number;
  createdAt: string;
  message?: string;
}

export type NormalizationInfo = NormalizationSuccess | NormalizationFailure;

export interface JobDetail extends ImportJobHistoryItem {
  type: ImportType;
  createdAt: string;
  logCount: number;
}

export interface JobLogEntry {
  id: number;
  createdAt: string;
  kind?: string;
  message?: string;
  [key: string]: unknown;
}

export interface JobLogsResponse {
  items: JobLogEntry[];
  hasMore: boolean;
  nextAfter: number | null;
}

export interface ImportQueueEntry {
  jobId: number;
  enqueuedAt: string;
  source: string;
  priority: number;
}

export interface ImportQueueResponse {
  queued: ImportQueueEntry[];
}

export interface Bouquet {
  id: number;
  name: string;
}

export type CatalogItemType = 'movie' | 'series';

interface CatalogItemBase {
  id: string;
  type: CatalogItemType;
  title: string;
}

export interface CatalogMovie extends CatalogItemBase {
  type: 'movie';
  year: number;
  genres: string[];
  poster: string;
}

export interface CatalogSeries extends CatalogItemBase {
  type: 'series';
  seasons: number;
  status: string;
}

export type CatalogItem = CatalogMovie | CatalogSeries;

export type BouquetSelection = Record<string, string[]>;

export interface BouquetsResponse {
  bouquets: Bouquet[];
  catalog: CatalogItem[];
  selected: BouquetSelection;
}

export interface SaveBouquetResponse {
  ok: boolean;
  updatedAt: string;
}

export interface LogListFilters {
  type?: string;
  status?: string;
  dateRange?: {
    from: string;
    to: string;
  };
}

export interface LogItem {
  id: number;
  jobId: number;
  type: ImportType;
  status: ImportJobStatus;
  startedAt: string;
  finishedAt: string;
  durationSec: number;
  inserted: number;
  updated: number;
  ignored: number;
  errors: number;
  errorSummary?: string;
}

export interface LogListResponse {
  items: LogItem[];
  filters: LogListFilters;
  page: number;
  pageSize: number;
  total: number;
}

export interface LogDetailResponse {
  id: number;
  content: string;
}

export type ConfigStatus = 'success' | 'error' | null;

export interface GeneralSettings {
  dbHost: string;
  dbPort: number;
  dbUser: string;
  dbName: string;
  apiBaseUrl: string;
  m3uLink: string;
  tmdbKeyMasked: boolean;
  xtreamUser: string;
  useXtreamApi: boolean;
  bouquetNormal: number | null;
  bouquetAdulto: number | null;
  ignoredPrefixes: string[];
  dbPassMasked: boolean;
  xtreamPassMasked: boolean;
  lastTestStatus: ConfigStatus;
  lastTestMessage: string | null;
  lastTestAt: string | null;
}

export interface SaveConfigPayload {
  dbHost: string;
  dbPort: number;
  dbUser: string;
  dbName: string;
  apiBaseUrl: string;
  m3uLink: string;
  tmdbKey: string | null;
  xtreamUser: string;
  useXtreamApi: boolean;
  bouquetNormal: number | null;
  bouquetAdulto: number | null;
  ignoredPrefixes: string[];
  dbPass: string | null;
  xtreamPass: string | null;
}

export interface ConfigSchemaField {
  type: 'string' | 'number' | 'password' | 'url' | 'boolean' | 'list';
  label: string;
  required: boolean;
  min?: number;
  max?: number;
}

export interface ConfigSchema {
  defaults: Record<string, unknown>;
  fields: Record<string, ConfigSchemaField>;
}

export interface ConfigSaveResponse {
  ok: boolean;
  settings: GeneralSettings;
}

export interface ConfigResetResponse {
  ok: boolean;
  settings: GeneralSettings;
}

export interface ConfigTestResponse {
  success: boolean;
  message: string;
  status: 'success' | 'error';
  testedAt?: string | null;
}

export interface XuiIntegrationOptions {
  tmdb: {
    enabled: boolean;
    apiKey?: string | null;
    language: string;
    region: string;
  };
  throttleMs: number;
  limitItems?: number | null;
  maxParallel?: number | null;
  categoryMapping: {
    movies: Record<string, number | string>;
    series: Record<string, number | string>;
  };
  bouquets: {
    movies?: number | string | null;
    series?: number | string | null;
    adult?: number | string | null;
  };
  adultCategories: Array<string | number>;
  adultKeywords: string[];
  ignore: {
    movies: { categories: Array<string | number>; prefixes: string[] };
    series: { categories: Array<string | number>; prefixes: string[] };
  };
  retry: {
    enabled: boolean;
    maxAttempts: number;
    backoffSeconds: number;
  };
}

export interface XuiIntegrationConfig {
  tenantId: string;
  xuiDbUri: string | null;
  xtreamBaseUrl: string | null;
  xtreamUsername: string | null;
  hasXtreamPassword: boolean;
  xuiApiUser?: string | null;
  tmdbKey?: string | null;
  ignorePrefixes?: string[];
  ignoreCategories?: Array<string | number>;
  options: XuiIntegrationOptions;
}

export interface SaveXuiIntegrationResponse {
  ok: boolean;
  config: XuiIntegrationConfig;
  requiresWorkerRestart: boolean;
}

export interface TenantSummary {
  id: string;
  name: string;
  createdAt: string | null;
}

export interface TenantCreationResponse {
  ok: boolean;
  tenant: TenantSummary;
  integration?: XuiIntegrationConfig;
}
