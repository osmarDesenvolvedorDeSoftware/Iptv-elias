import { AlertTriangle, CheckCircle2, MinusCircle, RefreshCcw } from 'lucide-react';

import { resolveJobStatusLabel } from '../../data/services/importService';
import type { JobDetail, NormalizationInfo } from '../../data/types';
import type { JobProgressSnapshot } from '../../hooks/useImportJobs';

const statusMap: Record<string, { label: string; badge: string; description: string }> = {
  idle: { label: 'Pronto', badge: 'bg-secondary', description: 'Aguardando próxima execução.' },
  queued: { label: 'Na fila', badge: 'bg-info text-dark', description: 'Aguardando processamento pelo worker.' },
  running: { label: 'Em execução', badge: 'bg-warning text-dark', description: 'Importação em andamento.' },
  finished: { label: 'Concluído', badge: 'bg-success', description: 'Importação finalizada com sucesso.' },
  failed: { label: 'Falhou', badge: 'bg-danger', description: 'Importação finalizada com erro.' },
};

interface MetricConfig {
  key: 'inserted' | 'updated' | 'ignored' | 'errors';
  label: string;
  icon: JSX.Element;
  emphasis: string;
}

const metrics: MetricConfig[] = [
  { key: 'inserted', label: 'Inseridos', icon: <CheckCircle2 size={18} aria-hidden="true" />, emphasis: 'text-success' },
  { key: 'updated', label: 'Atualizados', icon: <RefreshCcw size={18} aria-hidden="true" />, emphasis: 'text-primary' },
  { key: 'ignored', label: 'Ignorados', icon: <MinusCircle size={18} aria-hidden="true" />, emphasis: 'text-muted' },
  { key: 'errors', label: 'Erros', icon: <AlertTriangle size={18} aria-hidden="true" />, emphasis: 'text-danger' },
];

function formatDuration(seconds?: number): string {
  if (seconds === undefined || seconds === null) {
    return '—';
  }
  if (Number.isNaN(seconds)) {
    return '—';
  }
  const totalSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${remainingSeconds}s`;
  }
  return `${minutes}m ${remainingSeconds.toString().padStart(2, '0')}s`;
}

function formatDate(value?: string): string {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleString('pt-BR');
}

function resolveStatusInfo(status: string) {
  return statusMap[status] ?? statusMap.idle;
}

function renderNormalization(normalization?: NormalizationInfo) {
  if (!normalization) {
    return null;
  }

  if (normalization.status === 'failed') {
    return (
      <div className="alert alert-danger mb-0" role="alert">
        Normalização falhou: {normalization.message ?? 'motivo não informado.'}
      </div>
    );
  }

  const streamTotals = normalization.streams ?? {};
  const seriesTotals = normalization.series ?? {};

  return (
    <div className="alert alert-success mb-0" role="status">
      Normalização concluída — Streams analisados: {streamTotals.total ?? 0}, séries: {seriesTotals.total ?? 0}.
    </div>
  );
}

export interface ImportSummaryCardProps {
  job: JobDetail | null;
  progress: JobProgressSnapshot;
  status: string;
  loading: boolean;
}

export function ImportSummaryCard({ job, progress, status, loading }: ImportSummaryCardProps) {
  const statusInfo = resolveStatusInfo(status);
  const percent = progress.progress !== undefined ? Math.min(100, Math.max(0, Math.round(progress.progress * 100))) : null;

  return (
    <div className="card shadow-sm">
      <div className="card-header d-flex justify-content-between align-items-center">
        <span className="fw-semibold">Resumo da Execução</span>
        <span className={`badge ${statusInfo.badge}`}>{statusInfo.label}</span>
      </div>

      <div className="card-body d-flex flex-column gap-3">
        <p className="text-muted small mb-0">{statusInfo.description}</p>

        {percent !== null ? (
          <div>
            <div className="d-flex justify-content-between align-items-center mb-1 small text-muted">
              <span>Progresso</span>
              <span>{percent}%</span>
            </div>
            <div className="progress" style={{ height: '0.5rem' }} aria-hidden="true">
              <div className="progress-bar" role="progressbar" style={{ width: `${percent}%` }} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} />
            </div>
          </div>
        ) : null}

        <div className="row g-3">
          {metrics.map((metric) => (
            <div className="col-6 col-lg-3" key={metric.key}>
              <div className="border rounded-3 p-3 h-100 d-flex flex-column justify-content-between">
                <span className="text-uppercase text-muted small fw-semibold">{metric.label}</span>
                <span className={`fw-bold display-6 ${metric.emphasis} d-flex align-items-center gap-2`}>
                  {metric.icon}
                  {progress[metric.key] ?? 0}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="row g-3">
          <div className="col-12 col-lg-6">
            <div className="border rounded-3 p-3 h-100">
              <h6 className="text-uppercase text-muted small fw-semibold mb-3">Tempos</h6>
              <dl className="row mb-0 small">
                <dt className="col-5">Início</dt>
                <dd className="col-7">{formatDate(progress.startedAt)}</dd>
                <dt className="col-5">Conclusão</dt>
                <dd className="col-7">{formatDate(progress.finishedAt)}</dd>
                <dt className="col-5">Duração</dt>
                <dd className="col-7">{formatDuration(progress.durationSec)}</dd>
                <dt className="col-5">Previsão</dt>
                <dd className="col-7">{progress.etaSec ? formatDuration(progress.etaSec) : '—'}</dd>
              </dl>
            </div>
          </div>
          <div className="col-12 col-lg-6">
            <div className="border rounded-3 p-3 h-100">
              <h6 className="text-uppercase text-muted small fw-semibold mb-3">Detalhes</h6>
              {job ? (
                <dl className="row mb-0 small">
                  <dt className="col-5">Job</dt>
                  <dd className="col-7">#{job.id}</dd>
                  <dt className="col-5">Tipo</dt>
                  <dd className="col-7">{job.type ? resolveJobStatusLabel(job.type) : '—'}</dd>
                  <dt className="col-5">Log</dt>
                  <dd className="col-7">{job.logCount ?? 0} registros</dd>
                  <dt className="col-5">Origem</dt>
                  <dd className="col-7">{job.sourceTag ?? job.sourceTagFilmes ?? '—'}</dd>
                </dl>
              ) : (
                <p className="text-muted mb-0">Nenhuma importação selecionada.</p>
              )}
            </div>
          </div>
        </div>

        {job?.error ? (
          <div className="alert alert-danger mb-0 d-flex align-items-start gap-2" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <div>
              <strong>Erro:</strong> {job.error}
            </div>
          </div>
        ) : null}

        {renderNormalization(job?.normalization)}

        {loading ? (
          <div className="d-flex align-items-center gap-2 text-muted small" aria-live="polite">
            <span className="spinner-border spinner-border-sm" aria-hidden="true" />
            <span>Atualizando métricas…</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
