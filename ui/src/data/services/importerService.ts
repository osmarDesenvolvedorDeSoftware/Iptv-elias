import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import {
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
