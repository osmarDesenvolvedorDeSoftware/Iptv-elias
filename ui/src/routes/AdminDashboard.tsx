import { useCallback, useEffect, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { deleteUser, fetchDashboard, getUsers, updateUser } from '../data/services/adminService';
import { AdminRecentError, AdminStats, AdminUser } from '../data/types';
import { useToast } from '../providers/ToastProvider';
import { useAuth } from '../providers/AuthProvider';

export default function AdminDashboard() {
  const { push } = useToast();
  const { user: currentUser } = useAuth();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [recentErrors, setRecentErrors] = useState<AdminRecentError[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [dashboard, userList] = await Promise.all([
        fetchDashboard(),
        getUsers({ pageSize: 50 }),
      ]);
      setStats(dashboard.stats);
      setRecentErrors(dashboard.recentErrors);
      setUsers(userList.items);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível carregar o dashboard.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  async function handleToggleActive(target: AdminUser) {
    setUpdatingId(target.id);
    try {
      const response = await updateUser(target.id, { isActive: !target.isActive });
      setUsers((prev) => prev.map((item) => (item.id === target.id ? response.user : item)));
      push('Status atualizado com sucesso.', 'success');
    } catch (err) {
      const apiError = err as ApiError;
      push(apiError?.message ?? 'Não foi possível atualizar o usuário.', 'error');
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleResetPassword(target: AdminUser) {
    const password = window.prompt(`Nova senha para ${target.email}`);
    if (!password) {
      return;
    }

    setUpdatingId(target.id);
    try {
      await updateUser(target.id, { password });
      push('Senha redefinida com sucesso.', 'success');
    } catch (err) {
      const apiError = err as ApiError;
      push(apiError?.message ?? 'Não foi possível redefinir a senha.', 'error');
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleDelete(target: AdminUser) {
    if (target.id === currentUser?.id) {
      push('Você não pode remover a própria conta.', 'error');
      return;
    }

    const confirmed = window.confirm(`Remover definitivamente o usuário ${target.email}?`);
    if (!confirmed) {
      return;
    }

    setDeletingId(target.id);
    try {
      await deleteUser(target.id);
      setUsers((prev) => prev.filter((item) => item.id !== target.id));
      push('Usuário removido com sucesso.', 'success');
    } catch (err) {
      const apiError = err as ApiError;
      push(apiError?.message ?? 'Não foi possível remover o usuário.', 'error');
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="dashboard dashboard--admin">
      <header className="dashboard__header">
        <div>
          <h1 className="dashboard__title">Visão geral</h1>
          <p className="dashboard__subtitle">Acompanhe os usuários do painel e o status das integrações.</p>
        </div>
        <button type="button" className="btn btn-outline-secondary" onClick={() => void loadData()} disabled={isLoading}>
          {isLoading ? 'Atualizando…' : 'Atualizar dados'}
        </button>
      </header>

      {error ? (
        <div className="dashboard__alert" role="alert">
          {error}
        </div>
      ) : null}

      <section className="dashboard__grid dashboard__grid--stats mb-4">
        <StatCard label="Usuários cadastrados" value={stats?.totalUsers ?? 0} description="Total geral de contas no sistema." />
        <StatCard label="Usuários ativos" value={stats?.activeUsers ?? 0} description="Contas com acesso liberado." />
        <StatCard label="Jobs executados" value={stats?.totalJobs ?? 0} description="Importações registradas." />
        <StatCard label="Jobs com falha" value={stats?.failedJobs ?? 0} description="Execuções com erros recentes." tone="danger" />
      </section>

      <section className="card p-4 mb-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h2 className="h5 mb-0">Usuários</h2>
          <span className="text-muted">{stats?.lastSync ? `Último sync global: ${new Date(stats.lastSync).toLocaleString('pt-BR')}` : 'Sem sincronizações globais.'}</span>
        </div>

        <div className="table-responsive">
          <table className="table align-middle">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Último acesso</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.email}</td>
                  <td>{item.role}</td>
                  <td>
                    <span className={`badge ${item.isActive ? 'bg-success' : 'bg-secondary'}`}>
                      {item.isActive ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                  <td>{item.lastLogin ? new Date(item.lastLogin).toLocaleString('pt-BR') : '—'}</td>
                  <td className="d-flex gap-2">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-primary"
                      onClick={() => void handleToggleActive(item)}
                      disabled={updatingId === item.id}
                    >
                      {item.isActive ? 'Desativar' : 'Ativar'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => void handleResetPassword(item)}
                      disabled={updatingId === item.id}
                    >
                      Redefinir senha
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => void handleDelete(item)}
                      disabled={deletingId === item.id}
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="h5">Erros recentes</h2>
        {recentErrors.length === 0 ? (
          <p className="text-muted mb-0">Nenhum erro registrado nas últimas execuções.</p>
        ) : (
          <ul className="list-unstyled mb-0">
            {recentErrors.map((item) => (
              <li key={item.id} className="py-2 border-bottom">
                <strong>Job #{item.id}</strong> · {item.type} · Tenant {item.tenantId} · Usuário {item.userId}
                <div className="text-muted small">{item.finishedAt ? new Date(item.finishedAt).toLocaleString('pt-BR') : 'Em andamento'}</div>
                {item.error ? <div className="text-danger small">{item.error}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

interface StatCardProps {
  label: string;
  value: number;
  description: string;
  tone?: 'default' | 'danger';
}

function StatCard({ label, value, description, tone = 'default' }: StatCardProps) {
  return (
    <div className={`stat-card ${tone === 'danger' ? 'stat-card--danger' : ''}`}>
      <span className="stat-card__label">{label}</span>
      <strong className="stat-card__value">{value}</strong>
      <span className="stat-card__description">{description}</span>
    </div>
  );
}
