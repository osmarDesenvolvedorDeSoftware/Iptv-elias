import { Film, RefreshCw, ServerCog } from 'lucide-react';

import type { ImportJobAction } from '../../data/services/importService';
import { resolveJobStatusLabel } from '../../data/services/importService';
import type { ImportJobStatus, JobDetail } from '../../data/types';

const statusMap: Record<ImportJobStatus | 'idle', { label: string; badge: string; emoji: string }> = {
  idle: { label: 'Pronto para executar', badge: 'bg-secondary', emoji: '⚙️' },
  queued: { label: 'Na fila', badge: 'bg-info text-dark', emoji: '🟡' },
  running: { label: 'Rodando', badge: 'bg-warning text-dark', emoji: '🟡' },
  finished: { label: 'Concluído', badge: 'bg-success', emoji: '🟢' },
  failed: { label: 'Falhou', badge: 'bg-danger', emoji: '🔴' },
};

function formatDate(value?: string | null): string {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleString('pt-BR');
}

export interface ImportActionsCardProps {
  disabled: boolean;
  runningAction: ImportJobAction | null;
  status: ImportJobStatus | 'idle';
  currentJob: JobDetail | null;
  showConfigWarning?: boolean;
  onRunMovies: () => void;
  onRunSeries: () => void;
  onRunNormalization: () => void;
}

export function ImportActionsCard({
  disabled,
  runningAction,
  status,
  currentJob,
  showConfigWarning,
  onRunMovies,
  onRunSeries,
  onRunNormalization,
}: ImportActionsCardProps) {
  const statusInfo = statusMap[status] ?? statusMap.idle;

  const actionButtons = [
    {
      label: 'Importar Filmes',
      action: 'filmes' as ImportJobAction,
      icon: <Film size={18} aria-hidden="true" />,
      onClick: onRunMovies,
      variant: 'btn-primary',
    },
    {
      label: 'Importar Séries',
      action: 'series' as ImportJobAction,
      icon: <RefreshCw size={18} aria-hidden="true" />,
      onClick: onRunSeries,
      variant: 'btn-outline-primary',
    },
    {
      label: 'Normalizar Banco',
      action: 'normalize' as ImportJobAction,
      icon: <ServerCog size={18} aria-hidden="true" />,
      onClick: onRunNormalization,
      variant: 'btn-outline-secondary',
    },
  ];

  return (
    <div className="card shadow-sm">
      <div className="card-header d-flex justify-content-between align-items-center">
        <span className="fw-semibold">Ações de Importação</span>
        <span className={`badge ${statusInfo.badge} d-flex align-items-center gap-2`} aria-live="polite">
          <span>{statusInfo.emoji}</span>
          <span>{statusInfo.label}</span>
        </span>
      </div>

      <div className="card-body d-flex flex-column gap-3">
        <div className="d-flex flex-column flex-xl-row gap-3">
          {actionButtons.map((button) => (
            <button
              key={button.action}
              type="button"
              className={`btn ${button.variant} flex-fill d-flex align-items-center justify-content-center gap-2 py-3`}
              onClick={button.onClick}
              disabled={disabled}
            >
              {runningAction === button.action ? (
                <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
              ) : (
                button.icon
              )}
              <span className="fw-semibold text-uppercase small">{button.label}</span>
            </button>
          ))}
        </div>

        <section className="border rounded-3 p-3 bg-body-tertiary">
          <h6 className="text-uppercase text-muted small fw-semibold mb-3">Job Atual</h6>
          {currentJob ? (
            <dl className="row mb-0 small">
              <dt className="col-sm-4 col-md-3">Identificador</dt>
              <dd className="col-sm-8 col-md-9">#{currentJob.id}</dd>
              <dt className="col-sm-4 col-md-3">Tipo</dt>
              <dd className="col-sm-8 col-md-9">{resolveJobStatusLabel(currentJob.type)}</dd>
              <dt className="col-sm-4 col-md-3">Iniciado em</dt>
              <dd className="col-sm-8 col-md-9">{formatDate(currentJob.startedAt)}</dd>
              <dt className="col-sm-4 col-md-3">Operador</dt>
              <dd className="col-sm-8 col-md-9">{currentJob.user ?? '—'}</dd>
            </dl>
          ) : (
            <p className="mb-0 text-muted">Nenhuma importação selecionada ou em execução.</p>
          )}
        </section>

        {showConfigWarning ? (
          <div className="alert alert-warning mb-0" role="alert">
            ⚠️ Configure as credenciais em <strong>Configurações</strong> antes de iniciar uma importação.
          </div>
        ) : null}
      </div>
    </div>
  );
}
