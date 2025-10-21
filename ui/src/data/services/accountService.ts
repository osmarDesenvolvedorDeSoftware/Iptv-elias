import { get, post, put } from '../adapters/ApiAdapter';
import { UserConfigData } from '../types';

export async function fetchConfig(): Promise<UserConfigData> {
  const response = await get<UserConfigData>('/account/config');
  return response;
}

export async function saveConfig(payload: Partial<UserConfigData> & { password?: string | null }): Promise<UserConfigData> {
  const response = await put<UserConfigData>('/account/config', payload);
  return response;
}

export async function testConfig(): Promise<UserConfigData & { ok: boolean; message: string }> {
  return post<UserConfigData & { ok: boolean; message: string }>('/account/config/test');
}
