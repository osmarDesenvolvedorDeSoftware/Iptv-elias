import { MockAdapter } from '../adapters/MockAdapter';
import { LogDetailResponse, LogListResponse } from '../types';

/**
 * Lista logs recentes de importações.
 */
export async function getLogs(): Promise<LogListResponse> {
  return MockAdapter.fetch<LogListResponse>('logs.list.json');
}

/**
 * Carrega o conteúdo detalhado de um log específico.
 */
export async function getLogDetail(logId: number): Promise<LogDetailResponse> {
  return MockAdapter.fetch<LogDetailResponse>(`logs.${logId}.json`);
}
