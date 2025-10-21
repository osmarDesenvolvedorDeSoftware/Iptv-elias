import { useCallback, useEffect, useMemo, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import type { LogListResponse } from '../data/types';
import { resolveJobStatusLabel, type ImportJobAction } from '../data/services/importService';
import { ConfigStatusCard } from '../components/config/ConfigStatusCard';
import { ImportActionsCard } from '../components/imports/ImportActionsCard';
import { ImportHistoryTable } from '../components/imports/ImportHistoryTable';
import { ImportLogsViewer, type LogFilter } from '../components/imports/ImportLogsViewer';
import { ImportSummaryCard } from '../components/imports/ImportSummaryCard';
import { useConfig } from '../hooks/useConfig';
import { useImportJobs } from '../hooks/useImportJobs';
import { useToast } from '../providers/ToastProvider';

interface HistoryFiltersState {
  type: string;
  status: string;
}

const HISTORY_FILTER_STORAGE_KEY = 'iptv:imports:historyFilters';

function loadStoredFilters(): HistoryFiltersState {
  if (typeof window === 'undefined') {
    return { type: 'all', status: 'all' };
  }
  try {
    const raw = window.localStorage.getItem(HISTORY_FILTER_STORAGE_KEY);
    if (!raw) {
      return { type: 'all', status: 'all' };
    }
    const parsed = JSON.parse(raw) as Partial<HistoryFiltersState> | null;
    return {
      type: parsed?.type && typeof parsed.type === 'string' ? parsed.type : 'all',
      status: parsed?.status && typeof parsed.status === 'string' ? parsed.status : 'all',
    };
  } catch (error) {
    console.warn('Não foi possível restaurar filtros salvos.', error);
    return { type: 'all', status: 'all' };
  }
}

export default function Imports() {
  const { push } = useToast();
  const {
    config,
    loading: configLoading,
    error: configError,
    isValid: isConfigValid,
    testing: configTesting,
  } = useConfig();
  const {
    currentJob,
    status,
    progress,
    jobLoading,
    jobError,
    logs,
    logsLoading,
    logsError,
    isStreaming,
    startJob,
    loadJob,
    getHistory,
  } = useImportJobs();

  const [runningAction, setRunningAction] = useState<ImportJobAction | null>(null);
  const [logFilter, setLogFilter] = useState<LogFilter>('all');
  const [historyFilters, setHistoryFilters] = useState<HistoryFiltersState>(loadStoredFilters);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyData, setHistoryData] = useState<LogListResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    if (jobError) {
      push(jobError, 'error');
    }
  }, [jobError, push]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(HISTORY_FILTER_STORAGE_KEY, JSON.stringify(historyFilters));
  }, [historyFilters]);

  const loadHistory = useCallback(
    async (filters: HistoryFiltersState, page: number) => {
      setHistoryLoading(true);
      setHistoryError(null);
      try {
        const response = await getHistory({
          type: filters.type !== 'all' ? filters.type : undefined,
          status: filters.status !== 'all' ? filters.status : undefined,
          page,
        });
        setHistoryData(response);
        setHistoryPage(response.page ?? page);
      } catch (error) {
        const apiError = error as ApiError;
        setHistoryError(apiError?.message ?? 'Não foi possível carregar o histórico de importações.');
      } finally {
        setHistoryLoading(false);
      }
    },
    [getHistory],
  );

  useEffect(() => {
    void loadHistory(historyFilters, historyPage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleHistoryFiltersChange = useCallback(
    (next: HistoryFiltersState) => {
      setHistoryFilters(next);
      setHistoryPage(1);
      void loadHistory(next, 1);
    },
    [loadHistory],
  );

  const handleHistoryPageChange = useCallback(
    (page: number) => {
      setHistoryPage(page);
      void loadHistory(historyFilters, page);
    },
    [historyFilters, loadHistory],
  );

  const handleStartJob = useCallback(
    async (action: ImportJobAction) => {
      if (runningAction) {
        return;
      }
      setRunningAction(action);
      try {
        const job = await startJob(action);
        push(`${resolveJobStatusLabel(action)} enfileirada (job #${job.id}).`, 'success');
        void loadHistory(historyFilters, historyPage);
      } catch (error) {
        const apiError = error as ApiError;
        push(apiError?.message ?? 'Não foi possível iniciar a importação.', 'error');
      } finally {
        setRunningAction(null);
      }
    },
    [historyFilters, historyPage, loadHistory, push, runningAction, startJob],
  );

  const handleViewJob = useCallback(
    async (jobId: number) => {
      try {
        await loadJob(jobId);
        setLogFilter('all');
        push(`Job #${jobId} carregado no painel.`, 'info');
      } catch (error) {
        const apiError = error as ApiError;
        push(apiError?.message ?? 'Não foi possível carregar o job selecionado.', 'error');
      }
    },
    [loadJob, push],
  );

  const handleReloadLogs = useCallback(() => {
    if (!currentJob) {
      return;
    }
    void loadJob(currentJob.id);
  }, [currentJob, loadJob]);

  const databaseInfo = useMemo(
    () => ({
      host: config?.dbHost ?? '—',
      port: config?.dbPort ?? null,
      name: config?.dbName ?? '—',
    }),
    [config?.dbHost, config?.dbName, config?.dbPort],
  );

  const actionsDisabled = !isConfigValid || status === 'running' || status === 'queued' || jobLoading || Boolean(runningAction);

  const summaryLoading = jobLoading || status === 'running' || status === 'queued';

  return (
    <section className="container-fluid py-4">
      <header className="d-flex flex-column align-items-center mb-4 text-center">
        <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
          Dashboard / Importações
        </nav>
        <h1 className="display-6 mb-0">Painel de Importação</h1>
      </header>

      {configError ? (
        <div className="alert alert-danger" role="alert">
          {configError}
        </div>
      ) : null}

      {config ? (
        <div className="mb-4">
          <ConfigStatusCard
            database={databaseInfo}
            status={config.lastTestStatus ?? null}
            message={config.lastTestMessage}
            testedAt={config.lastTestAt}
            testing={configTesting}
            tmdbConfigured={Boolean(config.tmdbKeyMasked)}
            xtreamConfigured={Boolean(config.xtreamUser)}
            useXtreamApi={Boolean(config.useXtreamApi)}
          />
        </div>
      ) : configLoading ? (
        <div className="d-flex align-items-center gap-2 text-muted mb-4" aria-live="polite">
          <span className="spinner-border spinner-border-sm" aria-hidden="true" />
          <span>Carregando configurações…</span>
        </div>
      ) : null}

      <div className="row g-4 mt-1">
        <div className="col-12 col-xl-4 d-flex flex-column gap-4">
          <ImportActionsCard
            disabled={actionsDisabled}
            runningAction={runningAction}
            status={status}
            currentJob={currentJob}
            showConfigWarning={!isConfigValid}
            onRunMovies={() => handleStartJob('filmes')}
            onRunSeries={() => handleStartJob('series')}
            onRunNormalization={() => handleStartJob('normalize')}
          />
        </div>
        <div className="col-12 col-xl-8">
          <ImportSummaryCard job={currentJob} progress={progress} status={status} loading={summaryLoading} />
        </div>
      </div>

      <div className="row g-4 mt-1">
        <div className="col-12 col-xxl-7">
          <ImportLogsViewer
            logs={logs}
            filter={logFilter}
            onFilterChange={setLogFilter}
            loading={logsLoading}
            error={logsError}
            isStreaming={isStreaming}
            onRetry={currentJob ? handleReloadLogs : undefined}
          />
        </div>
        <div className="col-12 col-xxl-5">
          <ImportHistoryTable
            data={historyData}
            loading={historyLoading}
            error={historyError}
            filters={historyFilters}
            onFiltersChange={handleHistoryFiltersChange}
            onPageChange={handleHistoryPageChange}
            onRetry={() => loadHistory(historyFilters, historyPage)}
            onViewJob={handleViewJob}
          />
        </div>
      </div>
    </section>
  );
}
