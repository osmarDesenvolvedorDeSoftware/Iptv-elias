import { ChangeEvent, useEffect, useMemo, useState } from 'react';

import { LogModal } from '../components/LogModal';
import { getLogs } from '../data/services/logService';
import { LogItem, LogListResponse } from '../data/types';

interface FilterState {
  type: string;
  status: string;
  dateFrom: string;
  dateTo: string;
  search: string;
}

const statusClassMap: Record<string, string> = {
  running: 'badge bg-info text-dark',
  finished: 'badge bg-success',
  failed: 'badge bg-danger',
  queued: 'badge bg-warning text-dark',
};

function formatDate(value: string): string {
  return new Date(value).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds.toString().padStart(2, '0')}s`;
}

function matchesSearch(item: LogItem, query: string): boolean {
  if (!query) {
    return true;
  }

  const normalized = query.toLowerCase();
  return (
    item.id.toString().includes(normalized) ||
    item.jobId.toString().includes(normalized) ||
    item.type.toLowerCase().includes(normalized) ||
    (item.errorSummary ?? '').toLowerCase().includes(normalized)
  );
}

export default function Logs() {
  const [filters, setFilters] = useState<FilterState>({
    type: 'all',
    status: 'all',
    dateFrom: '',
    dateTo: '',
    search: '',
  });
  const [data, setData] = useState<LogListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalLogId, setModalLogId] = useState<number | null>(null);

  useEffect(() => {
    loadLogs();
  }, []);

  const filteredItems = useMemo(() => {
    if (!data) {
      return [] as LogItem[];
    }

    const fromDate = filters.dateFrom ? new Date(`${filters.dateFrom}T00:00:00`) : null;
    const toDate = filters.dateTo ? new Date(`${filters.dateTo}T23:59:59`) : null;

    return data.items.filter((item) => {
      if (filters.type !== 'all' && item.type !== filters.type) {
        return false;
      }

      if (filters.status !== 'all' && item.status !== filters.status) {
        return false;
      }

      if (fromDate && new Date(item.startedAt) < fromDate) {
        return false;
      }

      if (toDate && new Date(item.finishedAt) > toDate) {
        return false;
      }

      return matchesSearch(item, filters.search);
    });
  }, [data, filters]);

  const totalLogs = data?.total ?? filteredItems.length;

  async function loadLogs() {
    setLoading(true);
    setError(null);

    try {
      const response = await getLogs();
      setData(response);
      setFilters((current) => ({
        ...current,
        type: response.filters.type ?? 'all',
        status: response.filters.status ?? 'all',
        dateFrom: response.filters.dateRange?.from ?? '',
        dateTo: response.filters.dateRange?.to ?? '',
      }));
    } catch (loadError) {
      console.error(loadError);
      setError('Não foi possível carregar os relatórios mockados.');
    } finally {
      setLoading(false);
    }
  }

  function handleFilterChange(event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = event.target;
    setFilters((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function handleResetFilters() {
    setFilters({ type: 'all', status: 'all', dateFrom: '', dateTo: '', search: '' });
  }

  return (
    <section className="container-fluid py-4">
      <header className="d-flex flex-column align-items-center mb-4 text-center">
        <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
          Dashboard / Relatórios & Logs
        </nav>
        <h1 className="display-6 mb-0">Relatórios &amp; Logs</h1>
      </header>

      {error ? (
        <div className="alert alert-danger d-flex flex-column flex-md-row align-items-md-center justify-content-between" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-outline-light mt-3 mt-md-0" onClick={loadLogs}>
            Tentar novamente
          </button>
        </div>
      ) : null}

      <div className="card shadow-sm mb-4">
        <div className="card-body">
          <form className="row g-3" onSubmit={(event) => event.preventDefault()}>
            <div className="col-12 col-md-3">
              <label htmlFor="filter-date-from" className="form-label text-uppercase small text-muted">
                Início
              </label>
              <input
                id="filter-date-from"
                type="date"
                className="form-control"
                name="dateFrom"
                value={filters.dateFrom}
                onChange={handleFilterChange}
                disabled={loading}
              />
            </div>
            <div className="col-12 col-md-3">
              <label htmlFor="filter-date-to" className="form-label text-uppercase small text-muted">
                Fim
              </label>
              <input
                id="filter-date-to"
                type="date"
                className="form-control"
                name="dateTo"
                value={filters.dateTo}
                onChange={handleFilterChange}
                disabled={loading}
              />
            </div>
            <div className="col-12 col-md-2">
              <label htmlFor="filter-type" className="form-label text-uppercase small text-muted">
                Tipo
              </label>
              <select
                id="filter-type"
                className="form-control"
                name="type"
                value={filters.type}
                onChange={handleFilterChange}
                disabled={loading}
              >
                <option value="all">Todos</option>
                <option value="filmes">Filmes</option>
                <option value="series">Séries</option>
              </select>
            </div>
            <div className="col-12 col-md-2">
              <label htmlFor="filter-status" className="form-label text-uppercase small text-muted">
                Status
              </label>
              <select
                id="filter-status"
                className="form-control"
                name="status"
                value={filters.status}
                onChange={handleFilterChange}
                disabled={loading}
              >
                <option value="all">Todos</option>
                <option value="queued">Enfileirado</option>
                <option value="running">Em execução</option>
                <option value="finished">Concluído</option>
                <option value="failed">Com erros</option>
              </select>
            </div>
            <div className="col-12 col-md-2">
              <label htmlFor="filter-search" className="form-label text-uppercase small text-muted">
                Busca rápida
              </label>
              <input
                id="filter-search"
                type="search"
                className="form-control"
                placeholder="ID, job ou erro"
                name="search"
                value={filters.search}
                onChange={handleFilterChange}
                disabled={loading}
              />
            </div>
            <div className="col-12 d-flex justify-content-end gap-2">
              <button type="button" className="btn btn-outline-secondary" onClick={handleResetFilters} disabled={loading}>
                Limpar filtros
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card shadow-sm">
        <div className="card-header d-flex flex-column flex-lg-row justify-content-between gap-2 align-items-lg-center">
          <div>
            <h2 className="h5 mb-1">Histórico de execuções</h2>
            <p className="text-muted mb-0">Registros mockados de importações com status e totais agregados.</p>
          </div>
          <span className="text-muted small">Mostrando {filteredItems.length} de {totalLogs} registros</span>
        </div>
        <div className="table-responsive">
          <table className="table table-hover mb-0 align-items-center">
            <thead className="thead-light">
              <tr>
                <th>Início</th>
                <th>Fim</th>
                <th>Tipo</th>
                <th>Status</th>
                <th>Totais</th>
                <th>Erros</th>
                <th className="text-end">Ações</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(3)].map((_, index) => (
                  <tr key={index}>
                    <td colSpan={7}>
                      <div className="placeholder-glow">
                        <span className="placeholder col-12" style={{ height: '1.5rem' }} />
                      </div>
                    </td>
                  </tr>
                ))
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-5 text-muted">
                    Nenhum log encontrado para os filtros selecionados.
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => (
                  <tr key={item.id}>
                    <td>{formatDate(item.startedAt)}</td>
                    <td>{formatDate(item.finishedAt)}</td>
                    <td className="text-capitalize">{item.type}</td>
                    <td>
                      <span className={statusClassMap[item.status] ?? 'badge bg-secondary text-dark'}>{item.status}</span>
                    </td>
                    <td>
                      <div className="d-flex flex-column">
                        <span>Inseridos: {item.inserted}</span>
                        <span>Atualizados: {item.updated}</span>
                        <span>Ignorados: {item.ignored}</span>
                        <span>Duração: {formatDuration(item.durationSec)}</span>
                      </div>
                    </td>
                    <td>
                      {item.errors > 0 ? (
                        <span className="badge bg-danger">{item.errors}</span>
                      ) : (
                        <span className="badge bg-success">0</span>
                      )}
                    </td>
                    <td className="text-end">
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onClick={() => setModalLogId(item.id)}
                      >
                        Ver detalhes
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {modalLogId ? <LogModal logId={modalLogId} onClose={() => setModalLogId(null)} /> : null}
    </section>
  );
}
