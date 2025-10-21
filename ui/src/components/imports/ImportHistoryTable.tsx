import { type MouseEvent, useMemo, useState } from 'react';

import { resolveJobStatusLabel } from '../../data/services/importService';
import type { LogItem, LogListResponse } from '../../data/types';
import { LogModal } from '../LogModal';

interface HistoryFilters {
  type: string;
  status: string;
}

export interface ImportHistoryTableProps {
  data: LogListResponse | null;
  loading: boolean;
  error: string | null;
  filters: HistoryFilters;
  onFiltersChange: (filters: HistoryFilters) => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onViewJob: (jobId: number) => void;
}

const statusBadge: Record<string, string> = {
  running: 'bg-warning text-dark',
  queued: 'bg-info text-dark',
  finished: 'bg-success',
  failed: 'bg-danger',
};

const typeOptions = [
  { value: 'all', label: 'Todos' },
  { value: 'filmes', label: 'Filmes' },
  { value: 'series', label: 'Séries' },
  { value: 'normalization', label: 'Normalização' },
];

const statusOptions = [
  { value: 'all', label: 'Todos' },
  { value: 'running', label: 'Rodando' },
  { value: 'queued', label: 'Na fila' },
  { value: 'finished', label: 'Concluído' },
  { value: 'failed', label: 'Falhou' },
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) {
    return '—';
  }
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;
  if (minutes === 0) {
    return `${remaining}s`;
  }
  return `${minutes}m ${remaining.toString().padStart(2, '0')}s`;
}

export function ImportHistoryTable({
  data,
  loading,
  error,
  filters,
  onFiltersChange,
  onPageChange,
  onRetry,
  onViewJob,
}: ImportHistoryTableProps) {
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null);
  const items = data?.items ?? [];
  const currentPage = data?.page ?? 1;
  const totalPages = useMemo(() => {
    if (!data || data.pageSize === 0) {
      return 1;
    }
    return Math.max(1, Math.ceil(data.total / data.pageSize));
  }, [data]);

  const handleFilterChange = (name: keyof HistoryFilters, value: string) => {
    onFiltersChange({ ...filters, [name]: value });
  };

  const handleRowClick = (item: LogItem) => {
    if (item.logId) {
      setSelectedLogId(item.logId);
    }
  };

  const handleViewJob = (event: MouseEvent, jobId: number) => {
    event.stopPropagation();
    onViewJob(jobId);
  };

  return (
    <div className="card shadow-sm">
      <div className="card-header d-flex flex-column flex-lg-row justify-content-between gap-2 align-items-lg-center">
        <span className="fw-semibold">Histórico de Execuções</span>
        <div className="d-flex gap-2">
          <select
            className="form-select form-select-sm"
            value={filters.type}
            onChange={(event) => handleFilterChange('type', event.target.value)}
            disabled={loading}
            aria-label="Filtrar por tipo"
          >
            {typeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className="form-select form-select-sm"
            value={filters.status}
            onChange={(event) => handleFilterChange('status', event.target.value)}
            disabled={loading}
            aria-label="Filtrar por status"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="card-body p-0">
        {error ? (
          <div className="alert alert-danger rounded-0 d-flex justify-content-between align-items-start m-3" role="alert">
            <span>{error}</span>
            <button type="button" className="btn btn-sm btn-light" onClick={onRetry} disabled={loading}>
              Tentar novamente
            </button>
          </div>
        ) : null}

        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th scope="col">Início</th>
                <th scope="col">Tipo</th>
                <th scope="col">Duração</th>
                <th scope="col">Domínio</th>
                <th scope="col">Status</th>
                <th scope="col">Usuário</th>
                <th scope="col" className="text-end">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center text-muted py-5">
                    {loading ? (
                      <div className="d-flex align-items-center justify-content-center gap-2">
                        <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                        <span>Carregando histórico…</span>
                      </div>
                    ) : (
                      'Nenhuma execução encontrada.'
                    )}
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} role="button" onClick={() => handleRowClick(item)} className="align-middle">
                    <td>{formatDate(item.startedAt)}</td>
                    <td>{resolveJobStatusLabel(item.type)}</td>
                    <td>{formatDuration(item.durationSec)}</td>
                    <td>{item.sourceTag ?? item.sourceTagFilmes ?? '—'}</td>
                    <td>
                      <span className={`badge ${statusBadge[item.status] ?? 'bg-secondary'}`}>{item.status}</span>
                    </td>
                    <td>{item.user ?? '—'}</td>
                    <td className="text-end">
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onClick={(event) => handleViewJob(event, item.jobId)}
                      >
                        Ver no painel
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="d-flex justify-content-between align-items-center px-3 py-2 border-top bg-body-tertiary small text-muted">
          <span>
            Página {currentPage} de {totalPages} — {data?.total ?? items.length} execuções
          </span>
          <div className="btn-group" role="group" aria-label="Paginação de histórico">
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() => onPageChange(Math.max(1, currentPage - 1))}
              disabled={loading || currentPage <= 1}
            >
              Anterior
            </button>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
              disabled={loading || currentPage >= totalPages}
            >
              Próxima
            </button>
          </div>
        </div>
      </div>

      {selectedLogId ? <LogModal logId={selectedLogId} onClose={() => setSelectedLogId(null)} /> : null}
    </div>
  );
}
