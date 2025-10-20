import { get, post } from '../adapters/ApiAdapter';
import type { TenantCreationResponse, TenantSummary } from '../types';

export function listTenants() {
  return get<TenantSummary[]>('/tenants');
}

interface IntegrationPayload {
  xuiDbUri?: string | null;
  xtreamBaseUrl?: string | null;
  xtreamUsername?: string | null;
  xtreamPassword?: string | null;
  tmdbKey?: string | null;
  ignorePrefixes?: Array<string | number>;
  ignoreCategories?: Array<string | number>;
}

export function createTenant(payload: { id: string; name: string; integration?: IntegrationPayload }) {
  return post<TenantCreationResponse>('/tenants', payload);
}
