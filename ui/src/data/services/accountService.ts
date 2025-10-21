import { get, post, put } from '../adapters/ApiAdapter';
import { AccountConfigPayload, ParsedM3UResponse, UserConfigData } from '../types';

export async function fetchConfig(): Promise<UserConfigData> {
  const response = await get<UserConfigData>('/account/config');
  return response;
}

export async function parseM3U(link: string): Promise<ParsedM3UResponse> {
  const response = await post<ParsedM3UResponse>('/account/parse_m3u', { link });
  return response;
}

export async function saveAccountConfig(config: AccountConfigPayload): Promise<UserConfigData> {
  const response = await put<UserConfigData>('/account/config', config);
  return response;
}
