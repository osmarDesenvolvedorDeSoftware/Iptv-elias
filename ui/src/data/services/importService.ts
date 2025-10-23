import { API_BASE_URL } from '../../config';
import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import {
  ImportHistoryFilters,
  ImportJobKind,
  ImportListResponse,
  ImportRunResponse,
  ImportType,
  JobDetail,
  JobLogsResponse,
  JobStatusResponse,
  LogDetailResponse,
  LogListResponse,
} from '../types';

export type ImportJobAction = ImportType | 'normalize';

export interface JobLogsParams {
  after?: number | null;
  limit?: number;
}

export interface HistoryQuery extends ImportHistoryFilters {}

function ensureBaseUrl(): string {
  if (!API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL não configurada.');
  }
  return API_BASE_URL;
}

function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

export async function getImports(type: ImportType, params: { page?: number; pageSize?: number } = {}): Promise<ImportListResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<ImportListResponse>(`importacoes.${type}.json`);
  }

  const query = buildQuery(params);
  return get<ImportListResponse>(`/importacoes/${type}${query}`);
}

export async function runImport(type: ImportType): Promise<ImportRunResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<ImportRunResponse>(`importacoes.run.${type}.json`);
  }

  return post<ImportRunResponse>(`/importacoes/${type}/run`);
}

export async function runNormalization(): Promise<ImportRunResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<ImportRunResponse>('importacoes.run.normalize.json');
  }

  return post<ImportRunResponse>('/importacoes/normalize');
}

export async function startJob(action: ImportJobAction): Promise<ImportRunResponse> {
  if (action === 'normalize') {
    return runNormalization();
  }
  return runImport(action);
}

export async function getJob(jobId: number): Promise<JobDetail> {
  if (isMockEnabled) {
    return MockAdapter.fetch<JobDetail>(`jobs.detail.${jobId}.json`);
  }

  return get<JobDetail>(`/jobs/${jobId}`);
}

export async function getJobLogs(jobId: number, params: JobLogsParams = {}): Promise<JobLogsResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<JobLogsResponse>(`jobs.logs.${jobId}.json`);
  }

  const query = buildQuery({
    after: typeof params.after === 'number' ? params.after : undefined,
    limit: typeof params.limit === 'number' ? params.limit : undefined,
  });
  return get<JobLogsResponse>(`/jobs/${jobId}/logs${query}`);
}

export async function getJobStatus(jobId: number): Promise<JobStatusResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<JobStatusResponse>(`jobs.status.${jobId}.json`);
  }

  return get<JobStatusResponse>(`/jobs/${jobId}/status`);
}

export async function getHistory(filters: HistoryQuery = {}): Promise<LogListResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<LogListResponse>('logs.list.json');
  }

  const query = buildQuery({
    page: filters.page,
    pageSize: filters.pageSize,
    type: filters.type,
    status: filters.status,
  });

  return get<LogListResponse>(`/logs${query}`);
}

export async function getLogDetail(logId: number): Promise<LogDetailResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<LogDetailResponse>(`logs.${logId}.json`);
  }

  return get<LogDetailResponse>(`/logs/${logId}`);
}

export interface LogStreamOptions {
  token: string;
  tenantId?: string | null;
  lastEventId?: number | null;
  withStreamParam?: boolean;
}

export function openJobLogStream(jobId: number, options: LogStreamOptions): EventSource {
  const baseUrl = ensureBaseUrl();
  const url = new URL(`${baseUrl}/jobs/${jobId}/logs`);

  if (options.withStreamParam !== false) {
    url.searchParams.set('stream', '1');
  }

  if (options.token) {
    url.searchParams.set('token', options.token);
  }

  if (options.tenantId) {
    url.searchParams.set('tenant', options.tenantId);
  }

  if (options.lastEventId != null) {
    url.searchParams.set('lastEventId', String(options.lastEventId));
  }

  return new EventSource(url.toString());
}

export function resolveJobStatusLabel(status: ImportJobKind | ImportJobAction | string): string {
  switch (status) {
    case 'filmes':
      return 'Filmes';
    case 'series':
      return 'Séries';
    case 'normalize':
    case 'normalization':
      return 'Normalização';
    default:
      return status;
  }
}
