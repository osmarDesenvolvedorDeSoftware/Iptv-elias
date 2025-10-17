import { MockAdapter } from '../adapters/MockAdapter';
import { ConfigResponse } from '../types';

/**
 * Busca as configurações atuais do sistema mockado.
 */
export async function getConfig(): Promise<ConfigResponse> {
  return MockAdapter.fetch<ConfigResponse>('config.get.json');
}
