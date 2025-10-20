import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { isMockEnabled } from '../data/adapters/ApiAdapter';
import { ImportCard } from '../components/ImportCard';
import { ImportJobDetailsPanel } from '../components/ImportJobDetailsPanel';
import {
  getImports,
  getJobDetail,
  getJobLogs,
  runImport,
} from '../data/services/importerService';
import {
  ImportJobHistoryItem,
  ImportType,
  JobDetail,
  JobLogEntry,
} from '../data/types';
import { useToast } from '../providers/ToastProvider';

interface ImportCardState {
  loading: boolean;
  error: string | null;
  items: ImportJobHistoryItem[];
  actionLoading: boolean;
}

interface JobPanelState {
  selectedJobId: number | null;
  details: JobDetail | null;
  detailsLoading: boolean;
  detailsError: string | null;
  logs: JobLogEntry[];
  logsLoading: boolean;
  logsError: string | null;
  lastLogId: number | null;
}

const initialCardState: ImportCardState = {
  loading: true,
  error: null,
  items: [],
  actionLoading: false,
};

const createPanelState = (): JobPanelState => ({
  selectedJobId: null,
  details: null,
  detailsLoading: false,
  detailsError: null,
  logs: [],
  logsLoading: false,
  logsError: null,
  lastLogId: null,
});

const typeToTitle: Record<ImportType, string> = {
  filmes: 'Filmes',
  series: 'Séries',
};

export default function Importacao() {
  const { push } = useToast();
  const useMocks = isMockEnabled;
  const navigate = useNavigate();
  const [states, setStates] = useState<Record<ImportType, ImportCardState>>({
    filmes: { ...initialCardState },
    series: { ...initialCardState },
  });
  const [panels, setPanels] = useState<Record<ImportType, JobPanelState>>({
    filmes: createPanelState(),
    series: createPanelState(),
  });
  const panelsRef = useRef(panels);
  const normalizationWarningsRef = useRef(new Set<number>());
  const hasLoaded = !states.filmes.loading && !states.series.loading;

  useEffect(() => {
    panelsRef.current = panels;
  }, [panels]);

  useEffect(() => {
    loadImports('filmes');
    loadImports('series');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateState(
    type: ImportType,
    partial: Partial<ImportCardState> | ((current: ImportCardState) => ImportCardState),
  ) {
    setStates((prev) => {
      const current = prev[type];
      const next = typeof partial === 'function' ? partial(current) : { ...current, ...partial };

      return {
        ...prev,
        [type]: next,
      };
    });
  }

  const selectJob = useCallback((type: ImportType, jobId: number) => {
    setPanels((prev) => {
      const current = prev[type];
      if (current.selectedJobId === jobId) {
        return prev;
      }

      return {
        ...prev,
        [type]: {
          ...createPanelState(),
          selectedJobId: jobId,
          detailsLoading: true,
          logsLoading: true,
        },
      };
    });
  }, []);

  const loadJobDetail = useCallback(async (type: ImportType, jobId: number) => {
    setPanels((prev) => {
      const current = prev[type];
      if (!current || current.selectedJobId !== jobId) {
        return prev;
      }

      return {
        ...prev,
        [type]: {
          ...current,
          detailsLoading: true,
          detailsError: null,
        },
      };
    });

    try {
      const detail = await getJobDetail(jobId);
      setPanels((prev) => {
        const current = prev[type];
        if (!current || current.selectedJobId !== jobId) {
          return prev;
        }

        return {
          ...prev,
          [type]: {
            ...current,
            details: detail,
            detailsLoading: false,
            detailsError: null,
          },
        };
      });
    } catch (error) {
      const apiError = error as ApiError;
      setPanels((prev) => {
        const current = prev[type];
        if (!current || current.selectedJobId !== jobId) {
          return prev;
        }

        return {
          ...prev,
          [type]: {
            ...current,
            detailsLoading: false,
            detailsError: apiError?.message ?? 'Erro ao carregar detalhes do job.',
          },
        };
      });
    }
  }, []);

  const loadJobLogs = useCallback(
    async (type: ImportType, jobId: number, options: { reset?: boolean } = {}) => {
      const reset = Boolean(options.reset);
      const after = reset ? null : panelsRef.current[type].lastLogId;

      setPanels((prev) => {
        const current = prev[type];
        if (!current || current.selectedJobId !== jobId) {
          return prev;
        }

        const nextState: JobPanelState = {
          ...current,
          logsLoading: true,
          logsError: null,
        };

        if (reset) {
          nextState.logs = [];
          nextState.lastLogId = null;
        }

        return {
          ...prev,
          [type]: nextState,
        };
      });

      try {
        const response = await getJobLogs(
          jobId,
          reset
            ? { limit: 200 }
            : typeof after === 'number'
            ? { after }
            : {},
        );

        setPanels((prev) => {
          const current = prev[type];
          if (!current || current.selectedJobId !== jobId) {
            return prev;
          }

          const existingLogs = reset ? [] : current.logs;
          const existingIds = new Set(existingLogs.map((log) => log.id));
          const freshLogs = reset
            ? response.items
            : response.items.filter((entry) => !existingIds.has(entry.id));
          const mergedLogs = reset ? response.items : [...existingLogs, ...freshLogs];
          const lastItemId =
            mergedLogs.length > 0 ? mergedLogs[mergedLogs.length - 1].id : current.lastLogId;
          const nextCursor =
            typeof response.nextAfter === 'number'
              ? response.nextAfter
              : lastItemId ?? null;

          return {
            ...prev,
            [type]: {
              ...current,
              logs: mergedLogs,
              logsLoading: false,
              logsError: null,
              lastLogId: nextCursor,
            },
          };
        });
      } catch (error) {
        const apiError = error as ApiError;
        setPanels((prev) => {
          const current = prev[type];
          if (!current || current.selectedJobId !== jobId) {
            return prev;
          }

          return {
            ...prev,
            [type]: {
              ...current,
              logsLoading: false,
              logsError: apiError?.message ?? 'Erro ao carregar logs do job.',
            },
          };
        });
      }
    },
    [],
  );

  async function loadImports(type: ImportType) {
    updateState(type, { loading: true, error: null });

    try {
      const response = await getImports(type);
      updateState(type, { items: response.items, loading: false, error: null });

      const panel = panelsRef.current[type];
      if (response.items.length === 0) {
        if (
          panel.selectedJobId !== null ||
          panel.details !== null ||
          panel.logs.length > 0
        ) {
          setPanels((prev) => ({
            ...prev,
            [type]: createPanelState(),
          }));
        }
        return;
      }

      const preferred =
        response.items.find((job) => job.status === 'running' || job.status === 'queued') ??
        response.items[0];

      const stillSelected =
        panel.selectedJobId !== null &&
        response.items.some((job) => job.id === panel.selectedJobId);

      if (!stillSelected && preferred) {
        selectJob(type, preferred.id);
      }
    } catch (error) {
      const apiError = error as ApiError;
      updateState(type, {
        loading: false,
        error: apiError?.message ?? 'Erro ao consultar serviço de importação.',
      });
    }
  }

  async function handleRun(type: ImportType) {
    updateState(type, (current) => ({ ...current, actionLoading: true }));

    try {
      const response = await runImport(type);

      if (useMocks) {
        const simulatedJob: ImportJobHistoryItem = {
          id: response.jobId,
          startedAt: new Date().toISOString(),
          status: response.status,
          trigger: 'manual',
          user: 'Operador Demo',
          progress: response.status === 'running' ? 0 : undefined,
        };

        updateState(type, (current) => ({
          ...current,
          actionLoading: false,
          error: null,
          items: [simulatedJob, ...current.items].slice(0, 10),
        }));
        selectJob(type, simulatedJob.id);
      } else {
        await loadImports(type);
        updateState(type, (current) => ({ ...current, actionLoading: false }));
      }

      push(`Importação de ${typeToTitle[type]} enfileirada com sucesso!`, 'success');
    } catch (error) {
      const apiError = error as ApiError;
      push(apiError?.message ?? 'Não foi possível enfileirar a importação.', 'error');
      updateState(type, (current) => ({ ...current, actionLoading: false }));
    }
  }

  useEffect(() => {
    const jobId = panels.filmes.selectedJobId;
    if (!jobId) {
      return;
    }
    loadJobDetail('filmes', jobId);
    loadJobLogs('filmes', jobId, { reset: true });
  }, [panels.filmes.selectedJobId, loadJobDetail, loadJobLogs]);

  useEffect(() => {
    const jobId = panels.series.selectedJobId;
    if (!jobId) {
      return;
    }
    loadJobDetail('series', jobId);
    loadJobLogs('series', jobId, { reset: true });
  }, [panels.series.selectedJobId, loadJobDetail, loadJobLogs]);

  useEffect(() => {
    const panel = panels.filmes;
    const jobId = panel.selectedJobId;
    if (!jobId) {
      return;
    }
    const shouldPoll =
      !panel.details || panel.details.status === 'running' || panel.details.status === 'queued';
    if (!shouldPoll) {
      return;
    }

    const interval = window.setInterval(() => {
      loadJobDetail('filmes', jobId);
      loadJobLogs('filmes', jobId);
    }, 5000);

    return () => window.clearInterval(interval);
  }, [panels.filmes.selectedJobId, panels.filmes.details?.status, loadJobDetail, loadJobLogs]);

  useEffect(() => {
    const panel = panels.series;
    const jobId = panel.selectedJobId;
    if (!jobId) {
      return;
    }
    const shouldPoll =
      !panel.details || panel.details.status === 'running' || panel.details.status === 'queued';
    if (!shouldPoll) {
      return;
    }

    const interval = window.setInterval(() => {
      loadJobDetail('series', jobId);
      loadJobLogs('series', jobId);
    }, 5000);

    return () => window.clearInterval(interval);
  }, [panels.series.selectedJobId, panels.series.details?.status, loadJobDetail, loadJobLogs]);

  const handleReloadPanel = useCallback(
    (type: ImportType) => {
      const panel = panelsRef.current[type];
      if (!panel.selectedJobId) {
        return;
      }
      loadJobDetail(type, panel.selectedJobId);
      loadJobLogs(type, panel.selectedJobId, { reset: true });
    },
    [loadJobDetail, loadJobLogs],
  );

  useEffect(() => {
    const checkPanel = (panel: JobPanelState) => {
      const job = panel.details;
      if (!job || job.status !== 'failed') {
        return;
      }

      const hasNormalizationError = panel.logs.some((log) => log.kind === 'normalizationError');
      if (hasNormalizationError && !normalizationWarningsRef.current.has(job.id)) {
        push(
          `Normalização do job #${job.id} falhou. Revise as configurações de conexão com o XUI.`,
          'error',
        );
        normalizationWarningsRef.current.add(job.id);
      }
    };

    checkPanel(panels.filmes);
    checkPanel(panels.series);
  }, [panels.filmes.details, panels.filmes.logs, panels.series.details, panels.series.logs, push]);

  return (
    <section className="container-fluid py-4">
      <header className="d-flex flex-column align-items-center mb-4 text-center">
        <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
          Dashboard / Importação
        </nav>
        <h1 className="display-6 mb-0">Importação</h1>
      </header>

      <div className="row g-4">
        {(Object.keys(states) as ImportType[]).map((type) => {
          const cardState = states[type];
          const panelState = panels[type];

          return (
            <div className="col-12 col-xl-6" key={type}>
              <div className="d-flex flex-column gap-3">
                <ImportCard
                  title={typeToTitle[type]}
                  loading={cardState.loading}
                  error={cardState.error}
                  items={cardState.items}
                  actionLoading={cardState.actionLoading}
                  onRunNow={() => handleRun(type)}
                  onViewLog={() =>
                    push(`Visualização de log para ${typeToTitle[type]} ainda não disponível.`, 'info')
                  }
                  onConfigure={() => navigate('/configuracoes?tab=xui')}
                  onRetry={() => loadImports(type)}
                  onSelectJob={(jobId) => selectJob(type, jobId)}
                  selectedJobId={panelState.selectedJobId}
                />
                <ImportJobDetailsPanel
                  job={panelState.details}
                  loading={panelState.detailsLoading}
                  error={panelState.detailsError}
                  logs={panelState.logs}
                  logsLoading={panelState.logsLoading}
                  logsError={panelState.logsError}
                  onRetry={() => handleReloadPanel(type)}
                />
              </div>
            </div>
          );
        })}
      </div>

      {!hasLoaded ? (
        <div className="d-flex align-items-center justify-content-center gap-2 mt-4" aria-live="polite">
          <span className="spinner-border spinner-border-sm" aria-hidden="true" />
          <span>Preparando dados das importações…</span>
        </div>
      ) : null}
    </section>
  );
}
