import { deleteRequest, get, patch, post } from '../adapters/ApiAdapter';
import {
  AdminRecentError,
  AdminStats,
  AdminUser,
  AdminUserConfigSnapshot,
} from '../types';

interface DashboardResponse {
  stats: AdminStats;
  recentErrors: AdminRecentError[];
}

export interface AdminUserFilters {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: 'all' | 'active' | 'inactive';
}

export interface AdminUserListResponse {
  items: AdminUser[];
  page: number;
  pageSize: number;
  total: number;
}

export interface CreateAdminUserPayload {
  name: string;
  email: string;
  password: string;
  isAdmin?: boolean;
  isActive?: boolean;
  status?: 'active' | 'inactive';
  tenantName?: string;
}

export interface UpdateAdminUserPayload {
  name?: string;
  email?: string;
  password?: string;
  isAdmin?: boolean;
  isActive?: boolean;
  status?: 'active' | 'inactive';
}

export type AdminUserConfigResponse = AdminUserConfigSnapshot;

export async function fetchDashboard(): Promise<DashboardResponse> {
  return get<DashboardResponse>('/admin/dashboard');
}

export async function getUsers(filters: AdminUserFilters = {}): Promise<AdminUserListResponse> {
  const params = new URLSearchParams();

  if (filters.page) {
    params.set('page', String(filters.page));
  }

  if (filters.pageSize) {
    params.set('pageSize', String(filters.pageSize));
  }

  if (filters.search) {
    params.set('search', filters.search);
  }

  if (filters.status && filters.status !== 'all') {
    params.set('status', filters.status);
  }

  const query = params.toString();
  const path = query ? `/admin/users?${query}` : '/admin/users';
  return get<AdminUserListResponse>(path);
}

export async function createUser(payload: CreateAdminUserPayload): Promise<{ user: AdminUser }> {
  return post<{ user: AdminUser }>('/admin/users', payload);
}

export async function updateUser(
  userId: number,
  payload: UpdateAdminUserPayload,
): Promise<{ user: AdminUser }> {
  return patch<{ user: AdminUser }>(`/admin/users/${userId}`, payload);
}

export async function deleteUser(userId: number): Promise<void> {
  await deleteRequest(`/admin/users/${userId}`);
}

export async function getUserConfig(userId: number): Promise<AdminUserConfigResponse> {
  return get<AdminUserConfigResponse>(`/admin/users/${userId}/config`);
}

export async function resetUserConfig(userId: number): Promise<AdminUserConfigResponse> {
  return post<AdminUserConfigResponse>(`/admin/users/${userId}/config/reset`);
}
