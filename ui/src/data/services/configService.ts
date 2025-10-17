import { MockAdapter } from '../adapters/MockAdapter';
import { ConfigResponse, ConfigSaveResponse } from '../types';

/**
 * Busca as configurações atuais do sistema mockado.
 */
export async function getConfig(): Promise<ConfigResponse> {
  return MockAdapter.fetch<ConfigResponse>('config.get.json');
}

/**
 * Simula o salvamento de configurações e avalia se é necessário reiniciar workers.
 */
export async function saveConfig(config: ConfigResponse): Promise<ConfigSaveResponse> {
  await new Promise((resolve) => setTimeout(resolve, 400));

  const requiresWorkerRestart = config.importer.maxParallelJobs > 2;

  return {
    ok: true,
    requiresWorkerRestart,
  };
}
