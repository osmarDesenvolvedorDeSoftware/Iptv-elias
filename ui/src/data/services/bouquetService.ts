import { MockAdapter } from '../adapters/MockAdapter';
import { BouquetsResponse } from '../types';

/**
 * Carrega a estrutura de bouquets, catálogo completo e seleção atual.
 */
export async function getBouquets(): Promise<BouquetsResponse> {
  return MockAdapter.fetch<BouquetsResponse>('bouquets.list.json');
}
