import { ChangeEvent, FormEvent } from 'react';

import type { AdminUser } from '../../data/types';

export type StatusFilter = 'all' | 'active' | 'inactive';

interface UserTableProps {
  users: AdminUser[];
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
  searchInput: string;
  status: StatusFilter;
  onSearchInputChange: (value: string) => void;
  onSearchSubmit: () => void;
  onStatusChange: (value: StatusFilter) => void;
  onPageChange: (page: number) => void;
  onCreate: () => void;
  onEdit: (user: AdminUser) => void;
  onViewConfig: (user: AdminUser) => void;
  onDelete: (user: AdminUser) => void;
}

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: 'Todos' },
  { value: 'active', label: 'Ativos' },
  { value: 'inactive', label: 'Inativos' },
];

function formatDate(value?: string | null): string {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleString('pt-BR');
  } catch (error) {
    return value;
  }
}

export function UserTable({
  users,
  loading,
  page,
  pageSize,
  total,
  searchInput,
  status,
  onSearchInputChange,
  onSearchSubmit,
  onStatusChange,
  onPageChange,
  onCreate,
  onEdit,
  onViewConfig,
  onDelete,
}: UserTableProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const displayPage = Math.min(page, totalPages);

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearchSubmit();
  }

  function handleStatusChange(event: ChangeEvent<HTMLSelectElement>) {
    onStatusChange(event.target.value as StatusFilter);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    onSearchInputChange(event.target.value);
  }

  function handlePrevPage() {
    if (displayPage > 1) {
      onPageChange(displayPage - 1);
    }
  }

  function handleNextPage() {
    if (displayPage < totalPages) {
      onPageChange(displayPage + 1);
    }
  }

  const hasResults = users.length > 0;

  return (
    <section className="card shadow-sm">
      <div className="card-header d-flex flex-column flex-md-row justify-content-between gap-3 align-items-md-center">
        <div>
          <nav className="text-uppercase text-muted small mb-1" aria-label="breadcrumb">
            Administração / Contas IPTV
          </nav>
          <h1 className="h4 mb-0">Gerenciamento de contas</h1>
        </div>
        <button type="button" className="btn btn-primary" onClick={onCreate}>
          Nova conta
        </button>
      </div>

      <div className="card-body">
        <form className="row g-3 align-items-end" onSubmit={handleSearchSubmit}>
          <div className="col-12 col-lg-6">
            <label htmlFor="admin-account-search" className="form-label text-uppercase small text-muted">
              Buscar
            </label>
            <div className="input-group">
              <input
                id="admin-account-search"
                type="search"
                className="form-control"
                placeholder="Nome ou email"
                value={searchInput}
                onChange={handleInputChange}
              />
              <button type="submit" className="btn btn-outline-secondary" disabled={loading}>
                Pesquisar
              </button>
            </div>
          </div>

          <div className="col-12 col-lg-3">
            <label htmlFor="admin-account-status" className="form-label text-uppercase small text-muted">
              Status
            </label>
            <select
              id="admin-account-status"
              className="form-select"
              value={status}
              onChange={handleStatusChange}
              disabled={loading}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="col-12 col-lg-3 text-lg-end">
            <span className="text-muted small">
              Página {displayPage} de {totalPages} · {total}{' '}
              {total === 1 ? 'registro' : 'registros'}
            </span>
          </div>
        </form>
      </div>

      <div className="table-responsive">
        <table className="table table-hover align-middle mb-0">
          <thead className="table-light">
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Nome</th>
              <th scope="col">Email</th>
              <th scope="col">Status</th>
              <th scope="col">Sincronizações</th>
              <th scope="col" className="text-end">
                Ações
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="text-center py-4">
                  <div className="d-inline-flex align-items-center gap-2">
                    <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                    <span>Carregando contas…</span>
                  </div>
                </td>
              </tr>
            ) : null}

            {!loading && !hasResults ? (
              <tr>
                <td colSpan={6} className="text-center py-4 text-muted">
                  Nenhuma conta encontrada com os filtros aplicados.
                </td>
              </tr>
            ) : null}

            {!loading
              ? users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>
                      <div className="fw-semibold">{user.name}</div>
                      <div className="small text-muted">Tenant: {user.tenantName ?? user.tenantId}</div>
                    </td>
                    <td>
                      <div>{user.email}</div>
                      <div className="small text-muted">Último acesso: {formatDate(user.lastLogin)}</div>
                    </td>
                    <td>
                      <span
                        className={`badge ${user.isActive ? 'bg-success-subtle text-success-emphasis' : 'bg-secondary-subtle text-secondary-emphasis'}`}
                      >
                        {user.isActive ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td>
                      <div className="fw-semibold">{user.syncCount}</div>
                      <div className="small text-muted">Último sync: {formatDate(user.lastSync)}</div>
                    </td>
                    <td className="text-end">
                      <div className="btn-group btn-group-sm" role="group" aria-label={`Ações para ${user.email}`}>
                        <button type="button" className="btn btn-outline-secondary" onClick={() => onViewConfig(user)}>
                          Configurações
                        </button>
                        <button type="button" className="btn btn-outline-primary" onClick={() => onEdit(user)}>
                          Editar
                        </button>
                        <button type="button" className="btn btn-outline-danger" onClick={() => onDelete(user)}>
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>

      <div className="card-footer d-flex flex-column flex-md-row justify-content-between align-items-center gap-3">
        <div className="btn-group" role="group" aria-label="Paginação">
          <button type="button" className="btn btn-outline-secondary" onClick={handlePrevPage} disabled={displayPage <= 1}>
            Anterior
          </button>
          <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={handleNextPage}
            disabled={displayPage >= totalPages || total === 0}
          >
            Próxima
          </button>
        </div>
        <div className="text-muted small text-center text-md-end w-100 w-md-auto">
          Exibindo {hasResults ? users.length : 0} de {total} contas registradas.
        </div>
      </div>
    </section>
  );
}
