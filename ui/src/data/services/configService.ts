import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import { ConfigResponse, ConfigSaveResponse } from '../types';

/**
 * Busca as configurações atuais do sistema mockado.
 */
export async function getConfig(): Promise<ConfigResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<ConfigResponse>('config.get.json');
  }

  return get<ConfigResponse>('/config');
}

/**
 * Simula o salvamento de configurações e avalia se é necessário reiniciar workers.
 */
export async function saveConfig(config: ConfigResponse): Promise<ConfigSaveResponse> {
  if (isMockEnabled) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const requiresWorkerRestart = config.importer.maxParallelJobs > 2;

    return {
      ok: true,
      requiresWorkerRestart,
    };
  }

  return post<ConfigSaveResponse>('/config', config);
}
