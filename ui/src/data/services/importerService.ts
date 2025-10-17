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
  return MockAdapter.fetch<ImportListResponse>(`importacoes.${type}.json`);
}

/**
 * Enfileira uma nova importação e retorna o identificador do job criado.
 */
export async function runImport(type: ImportType): Promise<ImportRunResponse> {
  return MockAdapter.fetch<ImportRunResponse>(`importacoes.run.${type}.json`);
}

/**
 * Consulta o status de um job em execução.
 */
export async function getJobStatus(jobId: number): Promise<JobStatusResponse> {
  return MockAdapter.fetch<JobStatusResponse>(`jobs.status.${jobId}.json`);
}
