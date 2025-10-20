import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { isMockEnabled } from '../data/adapters/ApiAdapter';
import { ImportCard } from '../components/ImportCard';
import { getImports, runImport } from '../data/services/importerService';
import { ImportJobHistoryItem, ImportType } from '../data/types';
import { useToast } from '../providers/ToastProvider';

type ImportCardState = {
  loading: boolean;
  error: string | null;
  items: ImportJobHistoryItem[];
  actionLoading: boolean;
};

const initialState: ImportCardState = {
  loading: true,
  error: null,
  items: [],
  actionLoading: false,
};

const typeToTitle: Record<ImportType, string> = {
  filmes: 'Filmes',
  series: 'Séries',
};

export default function Importacao() {
  const { push } = useToast();
  const useMocks = isMockEnabled;
  const navigate = useNavigate();
  const [states, setStates] = useState<Record<ImportType, ImportCardState>>({
    filmes: { ...initialState },
    series: { ...initialState },
  });
  const hasLoaded = !states.filmes.loading && !states.series.loading;

  useEffect(() => {
    loadImports('filmes');
    loadImports('series');
  }, []);

  function updateState(
    type: ImportType,
    partial: Partial<ImportCardState> | ((current: ImportCardState) => ImportCardState),
  ) {
    setStates((prev) => {
      const current = prev[type];
      const next =
        typeof partial === 'function' ? partial(current) : { ...current, ...partial };

      return {
        ...prev,
        [type]: next,
      };
    });
  }

  async function loadImports(type: ImportType) {
    updateState(type, { loading: true, error: null });

    try {
      const response = await getImports(type);
      updateState(type, { items: response.items, loading: false, error: null });
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

          return (
            <div className="col-12 col-xl-6" key={type}>
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
                onConfigure={() =>
                  navigate('/configuracoes?tab=xui')
                }
                onRetry={() => loadImports(type)}
              />
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
