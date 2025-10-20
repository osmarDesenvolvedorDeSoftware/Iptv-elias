import { get, post } from '../adapters/ApiAdapter';
import type { SaveXuiIntegrationResponse, XuiIntegrationConfig } from '../types';

export function getXuiIntegrationConfig() {
  return get<XuiIntegrationConfig>('/integrations/xui');
}

export function saveXuiIntegrationConfig(payload: Partial<XuiIntegrationConfig> & { xtreamPassword?: string | null }) {
  return post<SaveXuiIntegrationResponse>('/integrations/xui', payload);
}
