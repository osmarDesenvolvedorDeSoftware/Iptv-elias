import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import { BouquetsResponse, SaveBouquetResponse } from '../types';

/**
 * Carrega a estrutura de bouquets, catálogo completo e seleção atual.
 */
export async function getBouquets(): Promise<BouquetsResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<BouquetsResponse>('bouquets.list.json');
  }

  return get<BouquetsResponse>('/bouquets');
}

/**
 * Simula a persistência do bouquet selecionado.
 */
export async function saveBouquet(_bouquetId: number, _items: string[]): Promise<SaveBouquetResponse> {
  if (isMockEnabled) {
    await new Promise((resolve) => setTimeout(resolve, 400));

    return {
      ok: true,
      updatedAt: new Date().toISOString(),
    };
  }

  return post<SaveBouquetResponse>(`/bouquets/${_bouquetId}`, { items: _items });
}
