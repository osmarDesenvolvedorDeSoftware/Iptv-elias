import { useEffect, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import {
  createUser,
  deleteUser,
  getUserConfig,
  getUsers,
  resetUserConfig,
  updateUser,
} from '../data/services/adminService';
import type { AdminUser, AdminUserConfigSnapshot } from '../data/types';
import { useAuth } from '../providers/AuthProvider';
import { useToast } from '../providers/ToastProvider';
import { StatusFilter, UserTable } from '../components/admin/UserTable';
import { UserFormModal } from '../components/admin/UserFormModal';
import { UserConfigModal } from '../components/admin/UserConfigModal';

const PAGE_SIZE = 10;

type FormPayload = {
  name: string;
  email: string;
  password?: string;
  isAdmin: boolean;
  isActive: boolean;
};

export default function AdminAccounts() {
  const { user: currentUser } = useAuth();
  const { push } = useToast();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  const [configOpen, setConfigOpen] = useState(false);
  const [configUser, setConfigUser] = useState<AdminUser | null>(null);
  const [configData, setConfigData] = useState<AdminUserConfigSnapshot | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configResetting, setConfigResetting] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadAccounts() {
      setLoading(true);
      setError(null);

      try {
        const response = await getUsers({
          page,
          pageSize: PAGE_SIZE,
          search: search ? search : undefined,
          status,
        });
        if (!cancelled) {
          setUsers(response.items);
          setTotal(response.total);
          if (response.items.length === 0 && response.total > 0 && page > 1) {
            setPage((current) => Math.max(1, current - 1));
            setRefreshToken((token) => token + 1);
          }
        }
      } catch (loadError) {
        const apiError = loadError as ApiError;
        if (!cancelled) {
          setError(apiError?.message ?? 'Não foi possível carregar as contas IPTV.');
          setUsers([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadAccounts();

    return () => {
      cancelled = true;
    };
  }, [page, search, status, refreshToken]);

  useEffect(() => {
    if (!configOpen || !configUser) {
      return;
    }

    let cancelled = false;
    setConfigLoading(true);
    setConfigData(null);

    async function loadConfig() {
      try {
        const response = await getUserConfig(configUser.id);
        if (!cancelled) {
          setConfigData(response);
        }
      } catch (configError) {
        const apiError = configError as ApiError;
        if (!cancelled) {
          push(apiError?.message ?? 'Não foi possível carregar as configurações IPTV.', 'error');
          setConfigOpen(false);
        }
      } finally {
        if (!cancelled) {
          setConfigLoading(false);
        }
      }
    }

    void loadConfig();

    return () => {
      cancelled = true;
    };
  }, [configOpen, configUser, push]);

  function handleSearchSubmit() {
    const trimmed = searchInput.trim();
    setPage(1);
    setSearch(trimmed);
    if (trimmed === search) {
      setRefreshToken((token) => token + 1);
    }
  }

  function handleStatusChange(value: StatusFilter) {
    setPage(1);
    setStatus(value);
    if (value === status) {
      setRefreshToken((token) => token + 1);
    }
  }

  function handleCreate() {
    setFormMode('create');
    setSelectedUser(null);
    setFormOpen(true);
  }

  function handleEdit(user: AdminUser) {
    setFormMode('edit');
    setSelectedUser(user);
    setFormOpen(true);
  }

  function handleViewConfig(user: AdminUser) {
    setConfigUser(user);
    setConfigOpen(true);
  }

  function closeConfigModal() {
    setConfigOpen(false);
    setConfigUser(null);
    setConfigData(null);
  }

  async function handleResetConfig() {
    if (!configUser) {
      return;
    }

    setConfigResetting(true);
    try {
      const response = await resetUserConfig(configUser.id);
      setConfigData(response);
      push('Painel XUI resetado com sucesso.', 'success');
    } catch (resetError) {
      const apiError = resetError as ApiError;
      push(apiError?.message ?? 'Não foi possível resetar o painel XUI.', 'error');
    } finally {
      setConfigResetting(false);
    }
  }

  async function handleFormSubmit(payload: FormPayload) {
    setFormSubmitting(true);

    try {
      if (formMode === 'create') {
        await createUser({
          name: payload.name,
          email: payload.email,
          password: payload.password ?? '',
          isAdmin: payload.isAdmin,
          isActive: payload.isActive,
          status: payload.isActive ? 'active' : 'inactive',
        });
        push('Conta criada com sucesso.', 'success');
        setFormOpen(false);
        setSelectedUser(null);
        setPage(1);
        setRefreshToken((token) => token + 1);
      } else if (selectedUser) {
        const response = await updateUser(selectedUser.id, {
          name: payload.name,
          email: payload.email,
          password: payload.password,
          isAdmin: payload.isAdmin,
          isActive: payload.isActive,
          status: payload.isActive ? 'active' : 'inactive',
        });
        setUsers((current) => current.map((item) => (item.id === response.user.id ? response.user : item)));
        setSelectedUser(response.user);
        push('Conta atualizada com sucesso.', 'success');
        setFormOpen(false);
      }
    } catch (submitError) {
      const apiError = submitError as ApiError;
      push(apiError?.message ?? 'Não foi possível salvar a conta IPTV.', 'error');
    } finally {
      setFormSubmitting(false);
    }
  }

  function handleDelete(user: AdminUser) {
    if (user.id === currentUser?.id) {
      push('Você não pode remover a própria conta.', 'error');
      return;
    }
    setDeleteTarget(user);
  }

  async function confirmDelete() {
    if (!deleteTarget) {
      return;
    }

    setDeleting(true);
    try {
      await deleteUser(deleteTarget.id);
      setUsers((current) => current.filter((item) => item.id !== deleteTarget.id));
      setTotal((current) => Math.max(0, current - 1));
      push('Conta excluída com sucesso.', 'success');
      setDeleteTarget(null);
      setRefreshToken((token) => token + 1);
    } catch (deleteError) {
      const apiError = deleteError as ApiError;
      push(apiError?.message ?? 'Não foi possível excluir a conta.', 'error');
    } finally {
      setDeleting(false);
    }
  }

  function closeForm() {
    setFormOpen(false);
    setSelectedUser(null);
  }

  return (
    <section className="container-fluid py-4">
      <header className="mb-4">
        <h1 className="h3 mb-1">Contas IPTV</h1>
        <p className="text-muted mb-0">Gerencie usuários, permissões e configurações específicas de cada painel.</p>
      </header>

      {error ? (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      ) : null}

      <UserTable
        users={users}
        loading={loading}
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        searchInput={searchInput}
        status={status}
        onSearchInputChange={setSearchInput}
        onSearchSubmit={handleSearchSubmit}
        onStatusChange={handleStatusChange}
        onPageChange={setPage}
        onCreate={handleCreate}
        onEdit={handleEdit}
        onViewConfig={handleViewConfig}
        onDelete={handleDelete}
      />

      <UserFormModal
        open={formOpen}
        mode={formMode}
        user={selectedUser ?? undefined}
        submitting={formSubmitting}
        onSubmit={handleFormSubmit}
        onClose={closeForm}
      />

      <UserConfigModal
        open={configOpen}
        config={configData}
        loading={configLoading}
        resetting={configResetting}
        onClose={closeConfigModal}
        onReset={handleResetConfig}
      />

      {deleteTarget ? (
        <>
          <div className="modal fade show" style={{ display: 'block' }} role="dialog" aria-modal="true">
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">Confirmar exclusão</h5>
                  <button type="button" className="btn-close" onClick={() => setDeleteTarget(null)} aria-label="Cancelar" />
                </div>
                <div className="modal-body">
                  Tem certeza que deseja excluir a conta <strong>{deleteTarget.email}</strong>? Esta ação é irreversível e removerá todas as configurações associadas.
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-link text-decoration-none" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                    Cancelar
                  </button>
                  <button type="button" className="btn btn-danger" onClick={confirmDelete} disabled={deleting}>
                    {deleting ? 'Excluindo…' : 'Excluir definitivamente'}
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div className="modal-backdrop fade show" />
        </>
      ) : null}
    </section>
  );
}
