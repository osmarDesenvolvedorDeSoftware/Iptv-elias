import { MockAdapter } from '../adapters/MockAdapter';
import { AuthLoginResponse } from '../types';

/**
 * Simula o fluxo de login retornando o contrato documentado.
 */
export async function login(): Promise<AuthLoginResponse> {
  return MockAdapter.fetch<AuthLoginResponse>('auth.login.json');
}
