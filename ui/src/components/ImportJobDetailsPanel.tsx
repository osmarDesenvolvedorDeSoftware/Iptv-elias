import { memo, useMemo } from 'react';

import { JobDetail, JobLogEntry, NormalizationInfo } from '../data/types';

const statusLabels: Record<JobDetail['status'], string> = {
  queued: 'Na fila',
  running: 'Executando',
  finished: 'Concluído',
  failed: 'Falhou',
};

const statusClassNames: Record<JobDetail['status'], string> = {
  queued: 'badge badge-secondary',
  running: 'badge badge-info',
  finished: 'badge badge-success',
  failed: 'badge badge-danger',
};

const dateTimeFormatter = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
});

const logTimeFormatter = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'medium',
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

function describeNormalization(normalization?: NormalizationInfo) {
  if (!normalization) {
    return null;
  }

  if (normalization.status === 'failed') {
    return normalization.message || 'Falha na normalização automática.';
  }

  const streams = normalization.streams || {};
  const series = normalization.series || {};
  return `Streams normalizados: ${streams.updated ?? 0}/${streams.total ?? 0}. Séries etiquetadas: ${series.tagged ?? 0}/${series.total ?? 0}.`;
}

function describeLog(entry: JobLogEntry): { content: string; preformatted?: boolean } {
  const kind = entry.kind;
  if (kind === 'summary') {
    const totals = (entry.totals as Record<string, number | undefined>) || {};
    return {
      content: `Resumo: +${totals.inserted ?? 0} inseridos, ${totals.updated ?? 0} atualizados, ${totals.ignored ?? 0} ignorados, ${totals.errors ?? 0} erros.`,
    };
  }

  if (kind === 'normalization') {
    const normalization = entry as JobLogEntry & { streams?: NormalizationInfo['streams']; series?: NormalizationInfo['series'] };
    const streams = normalization.streams || {};
    const series = normalization.series || {};
    return {
      content: `Normalização executada: streams atualizados ${streams.updated ?? 0}/${streams.total ?? 0}, filmes com tag ${streams.moviesTagged ?? 0}. Séries etiquetadas ${series.tagged ?? 0}/${series.total ?? 0}.`,
    };
  }

  if (kind === 'normalizationError') {
    return {
      content: `Falha na normalização: ${(entry.message as string) || 'erro desconhecido.'}`,
    };
  }

  if (kind === 'item') {
    const status = typeof entry.status === 'string' ? entry.status : '';
    const title = typeof entry.title === 'string' ? entry.title : '';
    const reason = typeof entry.reason === 'string' ? entry.reason : '';
    return {
      content: `${status ? `[${status}] ` : ''}${title}${reason ? ` — ${reason}` : ''}`,
    };
  }

  if (typeof entry.message === 'string') {
    return { content: entry.message };
  }

  const { id, createdAt, ...rest } = entry;
  return { content: JSON.stringify(rest, null, 2), preformatted: true };
}

interface ImportJobDetailsPanelProps {
  job: JobDetail | null;
  loading: boolean;
  error?: string | null;
  logs: JobLogEntry[];
  logsLoading: boolean;
  logsError?: string | null;
  onRetry?: () => void;
}

export const ImportJobDetailsPanel = memo(function ImportJobDetailsPanel({
  job,
  loading,
  error,
  logs,
  logsLoading,
  logsError,
  onRetry,
}: ImportJobDetailsPanelProps) {
  const progress = useMemo(() => formatProgress(job?.progress), [job?.progress]);

  if (!job && loading) {
    return (
      <div className="card" aria-busy="true">
        <div className="card-body">
          <div className="placeholder-glow" role="status" aria-live="polite">
            <div className="placeholder col-6 mb-2" style={{ height: '1.5rem' }} />
            <div className="placeholder col-12 mb-3" style={{ height: '2.5rem' }} />
            <div className="placeholder col-10 mb-2" style={{ height: '1.25rem' }} />
            <div className="placeholder col-8 mb-2" style={{ height: '1.25rem' }} />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card border-danger">
        <div className="card-body">
          <div className="alert alert-danger mb-0" role="alert">
            <div className="d-flex flex-column gap-2">
              <div>{error}</div>
              {onRetry ? (
                <button type="button" className="btn btn-outline-light btn-sm" onClick={onRetry}>
                  Tentar novamente
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="card">
        <div className="card-body">
          <p className="text-muted mb-0">Selecione um job para visualizar os detalhes.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card" aria-live="polite">
      <div className="card-header d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2">
        <div>
          <h3 className="h5 mb-1">Job #{job.id}</h3>
          <div className="small text-muted">Criado em {dateTimeFormatter.format(new Date(job.createdAt))}</div>
        </div>
        <span className={statusClassNames[job.status]}>{statusLabels[job.status]}</span>
      </div>
      <div className="card-body">
        <section className="mb-4">
          <h4 className="h6 text-uppercase text-muted">Progresso</h4>
          {job.status === 'running' ? (
            <div className="progress" aria-label="Progresso do job">
              <div
                className="progress-bar"
                style={{ width: `${progress ?? 0}%` }}
                aria-valuenow={progress ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                {progress !== null ? `${progress}%` : ''}
              </div>
            </div>
          ) : (
            <p className="mb-0 text-muted">
              Iniciado em {dateTimeFormatter.format(new Date(job.startedAt))}
              {job.finishedAt ? ` · Finalizado em ${dateTimeFormatter.format(new Date(job.finishedAt))}` : ''}
              {job.durationSec ? ` · Duração ${formatDuration(job.durationSec)}` : ''}
            </p>
          )}
          {job.sourceTag || job.sourceTagFilmes ? (
            <p className="mt-2 mb-0">
              <strong>Fonte predominante:</strong>{' '}
              {job.sourceTagFilmes || job.sourceTag}
            </p>
          ) : null}
          {job.error ? (
            <p className="mt-2 mb-0 text-danger">
              <strong>Erro:</strong> {job.error}
            </p>
          ) : null}
        </section>

        <section className="mb-4">
          <h4 className="h6 text-uppercase text-muted">Contadores</h4>
          <dl className="row mb-0">
            <dt className="col-sm-3">Inseridos</dt>
            <dd className="col-sm-3">{job.inserted ?? '—'}</dd>
            <dt className="col-sm-3">Atualizados</dt>
            <dd className="col-sm-3">{job.updated ?? '—'}</dd>
            <dt className="col-sm-3">Ignorados</dt>
            <dd className="col-sm-3">{job.ignored ?? '—'}</dd>
            <dt className="col-sm-3">Erros</dt>
            <dd className="col-sm-3">{job.errors ?? '—'}</dd>
          </dl>
        </section>

        <section className="mb-4">
          <h4 className="h6 text-uppercase text-muted">Normalização pré-importação</h4>
          {job.normalization ? (
            <div
              className={
                job.normalization.status === 'success'
                  ? 'alert alert-success'
                  : 'alert alert-warning'
              }
              role="status"
            >
              <div className="d-flex flex-column gap-1">
                <div>{describeNormalization(job.normalization)}</div>
                <small className="text-muted">
                  Registrado em {logTimeFormatter.format(new Date(job.normalization.createdAt))}
                </small>
              </div>
            </div>
          ) : (
            <p className="text-muted mb-0">Sem registros de normalização.</p>
          )}
        </section>

        <section>
          <h4 className="h6 text-uppercase text-muted">Logs</h4>
          {logsError ? (
            <div className="alert alert-danger" role="alert">
              {logsError}
              {onRetry ? (
                <div className="mt-2">
                  <button type="button" className="btn btn-outline-light btn-sm" onClick={onRetry}>
                    Recarregar
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="list-group" aria-live="polite">
            {logs.map((entry) => {
              const description = describeLog(entry);
              return (
                <div key={entry.id} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-start gap-3">
                    <div>
                      <div className="fw-semibold small text-muted">
                        {logTimeFormatter.format(new Date(entry.createdAt))}
                      </div>
                      {description.preformatted ? (
                        <pre className="mb-0 small">{description.content}</pre>
                      ) : (
                        <p className="mb-0">{description.content}</p>
                      )}
                    </div>
                    <span className="badge bg-light text-dark">#{entry.id}</span>
                  </div>
                </div>
              );
            })}
            {logs.length === 0 && !logsLoading ? (
              <div className="list-group-item text-muted">Nenhum log registrado.</div>
            ) : null}
            {logsLoading ? (
              <div className="list-group-item d-flex align-items-center gap-2 text-muted" aria-busy="true">
                <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                Carregando logs…
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
});
