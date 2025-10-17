import { ImportJobHistoryItem } from '../data/types';

const statusLabels: Record<ImportJobHistoryItem['status'], string> = {
  queued: 'Na fila',
  running: 'Executando',
  finished: 'Concluído',
  failed: 'Falhou',
};

const statusClassNames: Record<ImportJobHistoryItem['status'], string> = {
  queued: 'badge badge-secondary',
  running: 'badge badge-info',
  finished: 'badge badge-success',
  failed: 'badge badge-danger',
};

interface ImportCardProps {
  title: string;
  loading: boolean;
  error?: string | null;
  items: ImportJobHistoryItem[];
  onRetry?: () => void;
  onRunNow: () => void;
  onViewLog: () => void;
  onConfigure: () => void;
  actionLoading?: boolean;
}

const dateTimeFormatter = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
});

function formatDuration(durationSec?: number) {
  if (!durationSec) {
    return '—';
  }

  const minutes = Math.floor(durationSec / 60);
  const seconds = durationSec % 60;
  return `${minutes}m${seconds.toString().padStart(2, '0')}s`;
}

function formatProgress(progress?: number) {
  if (typeof progress !== 'number') {
    return null;
  }

  return Math.round(progress * 100);
}

export function ImportCard({
  title,
  loading,
  error,
  items,
  onRetry,
  onRunNow,
  onViewLog,
  onConfigure,
  actionLoading,
}: ImportCardProps) {
  const orderedItems = [...items].sort(
    (a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
  );
  const currentJob =
    orderedItems.find((job) => job.status === 'running' || job.status === 'queued') ||
    orderedItems[0];
  const history = orderedItems.slice(0, 5);
  const runningProgress =
    currentJob?.status === 'running' ? formatProgress(currentJob.progress) : null;

  return (
    <div className="card import-card">
      <div className="card-header d-flex align-items-center justify-content-between">
        <h2 className="h5 mb-0">{title}</h2>
        <div className="btn-group gap-2">
          <button
            type="button"
            className="btn btn-primary"
            onClick={onRunNow}
            disabled={actionLoading || loading}
          >
            {actionLoading ? 'Executando…' : 'Rodar agora'}
          </button>
          <button type="button" className="btn btn-outline-secondary" onClick={onViewLog}>
            Ver log
          </button>
          <button type="button" className="btn btn-outline-secondary" onClick={onConfigure}>
            Configurar
          </button>
        </div>
      </div>

      <div className="card-body">
        {loading ? (
          <div className="d-flex align-items-center gap-2 py-4">
            <span className="spinner-border spinner-border-sm" aria-hidden="true" />
            <span>Carregando informações…</span>
          </div>
        ) : error ? (
          <div className="alert alert-danger" role="alert">
            <div className="d-flex flex-column gap-2">
              <strong>Não foi possível carregar os dados.</strong>
              <span>{error}</span>
              {onRetry ? (
                <button type="button" className="btn btn-outline-light btn-sm" onClick={onRetry}>
                  Tentar novamente
                </button>
              ) : null}
            </div>
          </div>
        ) : history.length === 0 ? (
          <p className="text-muted mb-0">Nenhuma importação registrada.</p>
        ) : (
          <>
            {currentJob ? (
              <div className="mb-4">
                <div className="text-muted text-uppercase small">Status atual</div>
                <div className="d-flex align-items-center gap-3 flex-wrap">
                  <span className={statusClassNames[currentJob.status]}>
                    {statusLabels[currentJob.status]}
                  </span>
                  {currentJob.status === 'running' ? (
                    <div className="progress w-100 w-md-50" aria-label="Progresso da importação">
                      <div
                        className="progress-bar"
                        style={{ width: `${runningProgress ?? 0}%` }}
                        aria-valuenow={runningProgress ?? 0}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        {runningProgress !== null ? `${runningProgress}%` : ''}
                      </div>
                    </div>
                  ) : null}
                  {currentJob.status === 'finished' && currentJob.durationSec ? (
                    <span className="text-muted">{formatDuration(currentJob.durationSec)}</span>
                  ) : null}
                </div>
              </div>
            ) : null}

            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <thead>
                  <tr>
                    <th scope="col">ID</th>
                    <th scope="col">Início</th>
                    <th scope="col">Status</th>
                    <th scope="col">Inseridos</th>
                    <th scope="col">Atualizados</th>
                    <th scope="col">Ignorados</th>
                    <th scope="col">Erros</th>
                    <th scope="col">Duração</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((job) => (
                    <tr key={job.id}>
                      <td>#{job.id}</td>
                      <td>{dateTimeFormatter.format(new Date(job.startedAt))}</td>
                      <td>
                        <span className={statusClassNames[job.status]}>{statusLabels[job.status]}</span>
                      </td>
                      <td>{job.inserted ?? '—'}</td>
                      <td>{job.updated ?? '—'}</td>
                      <td>{job.ignored ?? '—'}</td>
                      <td>{job.errors ?? '—'}</td>
                      <td>{formatDuration(job.durationSec)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
