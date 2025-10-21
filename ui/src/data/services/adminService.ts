import { deleteRequest, get, patch } from '../adapters/ApiAdapter';
import { AdminRecentError, AdminStats, AdminUser } from '../types';

interface DashboardResponse {
  stats: AdminStats;
  recentErrors: AdminRecentError[];
}

interface UsersResponse {
  users: AdminUser[];
}

export async function fetchDashboard(): Promise<DashboardResponse> {
  return get<DashboardResponse>('/admin/dashboard');
}

export async function fetchUsers(): Promise<UsersResponse> {
  return get<UsersResponse>('/admin/users');
}

export async function updateUser(
  userId: number,
  payload: Partial<Pick<AdminUser, 'name' | 'role' | 'isActive'>> & { password?: string },
): Promise<{ user: AdminUser }> {
  return patch<{ user: AdminUser }>(`/admin/users/${userId}`, payload);
}

export async function deleteUser(userId: number): Promise<void> {
  await deleteRequest(`/admin/users/${userId}`);
}
