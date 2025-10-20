export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  tenantId: string;
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

export interface ConfigResponse {
  tmdb: {
    apiKey: string;
    language: string;
    region: string;
  };
  importer: {
    movieDelayMs: number;
    seriesDelayMs: number;
    maxParallelJobs: number;
    defaultCategories: string[];
    useImageCache: boolean;
  };
  notifications: {
    emailAlerts: boolean;
    webhookUrl: string | null;
  };
}

export interface ConfigSaveResponse {
  ok: boolean;
  requiresWorkerRestart: boolean;
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
  options: XuiIntegrationOptions;
}

export interface SaveXuiIntegrationResponse {
  ok: boolean;
  config: XuiIntegrationConfig;
  requiresWorkerRestart: boolean;
}
