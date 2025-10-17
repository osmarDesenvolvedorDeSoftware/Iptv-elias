import { get, isMockEnabled } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import { LogDetailResponse, LogListResponse } from '../types';

/**
 * Lista logs recentes de importações.
 */
export async function getLogs(): Promise<LogListResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<LogListResponse>('logs.list.json');
  }

  return get<LogListResponse>('/logs');
}

/**
 * Carrega o conteúdo detalhado de um log específico.
 */
export async function getLogDetail(logId: number): Promise<LogDetailResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<LogDetailResponse>(`logs.${logId}.json`);
  }

  return get<LogDetailResponse>(`/logs/${logId}`);
}
