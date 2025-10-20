import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import {
  JobDetail,
  JobLogsResponse,
  ImportListResponse,
  ImportRunResponse,
  ImportType,
  JobStatusResponse,
} from '../types';

/**
 * Retorna o histórico e status atuais das importações de filmes ou séries.
 */
export async function getImports(type: ImportType): Promise<ImportListResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<ImportListResponse>(`importacoes.${type}.json`);
  }

  return get<ImportListResponse>(`/importacoes/${type}`);
}

/**
 * Enfileira uma nova importação e retorna o identificador do job criado.
 */
export async function runImport(type: ImportType): Promise<ImportRunResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<ImportRunResponse>(`importacoes.run.${type}.json`);
  }

  return post<ImportRunResponse>(`/importacoes/${type}/run`);
}

/**
 * Consulta o status de um job em execução.
 */
export async function getJobStatus(jobId: number): Promise<JobStatusResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<JobStatusResponse>(`jobs.status.${jobId}.json`);
  }

  return get<JobStatusResponse>(`/jobs/${jobId}/status`);
}

export async function getJobDetail(jobId: number): Promise<JobDetail> {
  if (isMockEnabled) {
    return MockAdapter.fetch<JobDetail>(`jobs.detail.${jobId}.json`);
  }

  return get<JobDetail>(`/jobs/${jobId}`);
}

interface JobLogsParams {
  after?: number | null;
  limit?: number;
}

export async function getJobLogs(jobId: number, params: JobLogsParams = {}): Promise<JobLogsResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<JobLogsResponse>(`jobs.logs.${jobId}.json`);
  }

  const search = new URLSearchParams();
  if (typeof params.after === 'number') {
    search.set('after', String(params.after));
  }
  if (typeof params.limit === 'number') {
    search.set('limit', String(params.limit));
  }

  const query = search.toString();
  const suffix = query ? `?${query}` : '';
  return get<JobLogsResponse>(`/jobs/${jobId}/logs${suffix}`);
}
