import type { ApiError } from '../adapters/ApiAdapter';
import { get, isMockEnabled, post } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';
import { AuthLoginResponse } from '../types';

const MOCK_EMAIL = 'operador@tenant.com';
const MOCK_PASSWORD = 'admin123';

export interface LoginPayload {
  email: string;
  password: string;
}

export async function login(payload: LoginPayload): Promise<AuthLoginResponse> {
  if (isMockEnabled) {
    const response = await MockAdapter.fetch<AuthLoginResponse>('auth.login.json');

    if (
      payload.email.trim().toLowerCase() !== response.user.email.toLowerCase() ||
      payload.password !== MOCK_PASSWORD
    ) {
      throw {
        message: 'Credenciais inválidas. Utilize o usuário e senha de demonstração.',
        code: 'invalid_credentials',
      } as ApiError;
    }

    return response;
  }

  return post<AuthLoginResponse>('/auth/login', payload, { skipAuth: true });
}

export async function refresh(refreshToken: string): Promise<AuthLoginResponse> {
  if (isMockEnabled) {
    const response = await MockAdapter.fetch<AuthLoginResponse>('auth.login.json');
    return {
      ...response,
      token: `${response.token}-refresh`,
    };
  }

  return post<AuthLoginResponse>('/auth/refresh', { refreshToken }, { skipAuth: true });
}

export async function me(): Promise<AuthLoginResponse> {
  if (isMockEnabled) {
    return MockAdapter.fetch<AuthLoginResponse>('auth.login.json');
  }

  return get<AuthLoginResponse>('/auth/me');
}

export const authMockCredentials = { email: MOCK_EMAIL, password: MOCK_PASSWORD };
