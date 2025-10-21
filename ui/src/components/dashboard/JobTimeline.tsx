import { motion } from 'framer-motion';
import type { ComponentType } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  PauseCircle,
  PlayCircle,
  XCircle,
} from 'lucide-react';

import type { DashboardJobStatus, RecentJobSummary } from '../../data/services/dashboardService';

interface JobTimelineProps {
  jobs: RecentJobSummary[];
  isLoading?: boolean;
}

interface StatusMeta {
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  tone: 'success' | 'danger' | 'info' | 'warning';
  label: string;
}

const STATUS_META: Record<DashboardJobStatus, StatusMeta> = {
  success: { icon: CheckCircle2, tone: 'success', label: 'Concluído' },
  error: { icon: XCircle, tone: 'danger', label: 'Falhou' },
  running: { icon: PlayCircle, tone: 'info', label: 'Em execução' },
  queued: { icon: Clock, tone: 'warning', label: 'Em fila' },
  cancelled: { icon: PauseCircle, tone: 'warning', label: 'Cancelado' },
};

export function JobTimeline({ jobs, isLoading }: JobTimelineProps) {
  if (isLoading) {
    return (
      <ul className="dashboard-timeline" aria-busy="true">
        {Array.from({ length: 5 }).map((_, index) => (
          <li key={index} className="dashboard-timeline__item">
            <span className="dashboard-timeline__icon dashboard-timeline__icon--loading">
              <Loader2 size={18} className="spin" />
            </span>
            <div className="dashboard-timeline__content">
              <span className="skeleton skeleton--text" style={{ width: '60%' }} />
              <span className="skeleton skeleton--text" style={{ width: '40%' }} />
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (!jobs.length) {
    return (
      <div className="dashboard-timeline__empty">
        <AlertTriangle size={20} /> Nenhuma execução recente encontrada.
      </div>
    );
  }

  return (
    <ul className="dashboard-timeline">
      {jobs.map((job, index) => {
        const meta = STATUS_META[job.status] ?? STATUS_META.queued;
        const Icon = meta.icon;

        return (
          <motion.li
            key={job.id}
            className="dashboard-timeline__item"
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <span className={`dashboard-timeline__icon dashboard-timeline__icon--${meta.tone}`} title={meta.label}>
              <Icon size={18} strokeWidth={1.75} />
            </span>
            <div className="dashboard-timeline__content">
              <div className="dashboard-timeline__row">
                <strong>{job.name}</strong>
                {job.tenantName ? <span className="dashboard-timeline__tenant">{job.tenantName}</span> : null}
              </div>
              <div className="dashboard-timeline__meta">
                <span title={formatFullDate(job.startedAt)}>Iniciado {formatRelative(job.startedAt)}</span>
                {job.durationSeconds ? <span>Duração {formatDuration(job.durationSeconds)}</span> : null}
                {job.message ? (
                  <span className="dashboard-timeline__message" title={job.message}>
                    {job.message}
                  </span>
                ) : null}
              </div>
            </div>
          </motion.li>
        );
      })}
    </ul>
  );
}

function formatRelative(dateInput?: string | null) {
  if (!dateInput) {
    return 'agora';
  }

  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) {
    return 'agora';
  }

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.round(diffMs / 60000);

  if (diffMinutes <= 0) {
    return 'agora';
  }

  if (diffMinutes < 60) {
    return `há ${diffMinutes} min`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `há ${diffHours} h`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `há ${diffDays} dia${diffDays > 1 ? 's' : ''}`;
}

function formatFullDate(dateInput?: string | null) {
  if (!dateInput) {
    return '';
  }

  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

function formatDuration(seconds: number) {
  const totalSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainder = totalSeconds % 60;

  if (minutes === 0) {
    return `${remainder}s`;
  }

  if (remainder === 0) {
    return `${minutes}min`;
  }

  return `${minutes}min ${remainder}s`;
}
