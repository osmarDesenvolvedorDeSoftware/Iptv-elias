import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
  Line,
  LineChart,
} from 'recharts';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Building2, Activity, RefreshCw, ServerCog, Users2 } from 'lucide-react';

import { ChartCard } from '../components/dashboard/ChartCard';
import { JobTimeline } from '../components/dashboard/JobTimeline';
import { StatCard, StatTone } from '../components/dashboard/StatCard';
import {
  DashboardMetrics,
  DashboardJobStatus,
  fetchDashboardMetrics,
} from '../data/services/dashboardService';
import { useTheme } from '../providers/ThemeProvider';

const POLLING_INTERVAL_MS = 30_000;

const STATUS_TONE: Record<DashboardJobStatus, StatTone> = {
  success: 'success',
  error: 'danger',
  running: 'info',
  queued: 'warning',
  cancelled: 'warning',
};

const statusLabels: Record<DashboardJobStatus, string> = {
  success: 'Sucesso',
  error: 'Erro',
  running: 'Em execução',
  queued: 'Em fila',
  cancelled: 'Cancelado',
};

export default function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [updateLabel, setUpdateLabel] = useState('Sincronizando…');
  const abortRef = useRef<AbortController | null>(null);

  const { mode } = useTheme();

  const primaryColor = useCssVariable('--iptv-primary', '#2563eb', mode);
  const surfaceBorder = useCssVariable('--iptv-surface-border', '#e2e8f0', mode);
  const textMuted = useCssVariable('--iptv-text-muted', '#64748b', mode);
  const successColor = useCssVariable('--iptv-success', '#16a34a', mode);
  const dangerColor = useCssVariable('--iptv-danger', '#dc2626', mode);
  const infoColor = useCssVariable('--iptv-info', '#0ea5e9', mode);

  const numberFormatter = useMemo(() => new Intl.NumberFormat('pt-BR'), []);
  const dayFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat('pt-BR', {
        day: '2-digit',
        month: 'short',
      }),
    [],
  );

  const loadMetrics = useCallback(
    async ({ background = false }: { background?: boolean } = {}) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      if (background) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }

      try {
        const data = await fetchDashboardMetrics(controller.signal);
        setMetrics(data);
        setError(null);
        setLastUpdatedAt(Date.now());
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }

        const message = err instanceof Error ? err.message : 'Não foi possível carregar o dashboard.';
        setError(message);
      } finally {
        if (!background) {
          setIsLoading(false);
        }
        setIsRefreshing(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadMetrics();
    const intervalId = window.setInterval(() => {
      void loadMetrics({ background: true });
    }, POLLING_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
      abortRef.current?.abort();
    };
  }, [loadMetrics]);

  useEffect(() => {
    if (!lastUpdatedAt) {
      setUpdateLabel(isLoading ? 'Sincronizando…' : 'Atualização pendente');
      return;
    }

    function updateRelativeLabel() {
      setUpdateLabel(formatTimeDistance(lastUpdatedAt));
    }

    updateRelativeLabel();
    const timer = window.setInterval(updateRelativeLabel, 1_000);

    return () => {
      window.clearInterval(timer);
    };
  }, [isLoading, lastUpdatedAt]);

  const jobHistory = metrics?.jobHistory ?? [];
  const durationHistory = metrics?.averageImportDuration ?? [];
  const streamVolume = metrics?.streamVolume ?? [];
  const recentJobs = metrics?.recentJobs ?? [];
  const tenants = metrics?.tenants ?? [];

  const totalStatusCount = metrics?.statusSummary.reduce((acc, item) => acc + item.count, 0) ?? 0;

  return (
    <section className="dashboard">
      <header className="dashboard__header">
        <div>
          <h1 className="dashboard__title">Visão geral</h1>
          <p className="dashboard__subtitle">Acompanhe jobs, tenants e sincronizações em tempo real.</p>
        </div>
        <div className="dashboard__header-actions">
          <button
            type="button"
            className="dashboard__refresh"
            onClick={() => void loadMetrics({ background: true })}
            disabled={isRefreshing}
          >
            <RefreshCw size={16} className={isRefreshing ? 'spin' : ''} />
            {isRefreshing ? 'Atualizando…' : 'Atualizar agora'}
          </button>
          <span className="dashboard__timestamp" aria-live="polite">
            Atualizado {updateLabel}
          </span>
        </div>
      </header>

      {error ? (
        <div className="dashboard__alert" role="alert">
          {error}
        </div>
      ) : null}

      <div className="dashboard__grid dashboard__grid--stats">
        <StatCard
          label="Tenants ativos"
          value={metrics ? numberFormatter.format(metrics.tenantCount) : '—'}
          description="Tenants configurados com integrações ativas."
          icon={Users2}
          accent="primary"
          tooltip="Quantidade total de tenants com integrações configuradas."
          isLoading={isLoading && !metrics}
        />

        <StatCard
          label="Jobs executados"
          value={metrics ? numberFormatter.format(metrics.totalJobs) : '—'}
          description="Total acumulado de jobs registrados."
          icon={ServerCog}
          accent="success"
          tooltip="Quantidade total de execuções de importação processadas."
          isLoading={isLoading && !metrics}
        />

        <StatCard
          label="Status das últimas execuções"
          value={totalStatusCount > 0 ? `${totalStatusCount} jobs` : '—'}
          description="Distribuição das execuções mais recentes."
          icon={Activity}
          accent="info"
          tooltip="Resumo dos últimos jobs por status."
          chips={(metrics?.statusSummary ?? []).map((item) => ({
            label: statusLabels[item.status],
            value: numberFormatter.format(item.count),
            tone: STATUS_TONE[item.status],
          }))}
          isLoading={isLoading && !metrics}
        />

        <StatCard
          label="Últimas sincronizações"
          value={
            tenants.length
              ? `${formatTenantRelative(tenants[0].lastSyncAt)} · ${tenants[0].tenantName}`
              : 'Aguardando sincronização'
          }
          description="Monitoramento das sincronizações por tenant."
          icon={Building2}
          accent="warning"
          tooltip="Tenants mais recentes e atrasados nas sincronizações."
          isLoading={isLoading && !metrics}
          footer={
            tenants.length ? (
              <ul className="dashboard-sync-list">
                {tenants.slice(0, 3).map((tenant) => (
                  <li key={tenant.tenantId}>
                    <span className={`status-dot status-dot--${tenant.status}`} aria-hidden="true" />
                    <span className="dashboard-sync-list__tenant">{tenant.tenantName}</span>
                    <span className="dashboard-sync-list__time" title={formatFullDate(tenant.lastSyncAt)}>
                      {formatTenantRelative(tenant.lastSyncAt)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : undefined
          }
        />
      </div>

      <div className="dashboard__grid dashboard__grid--charts">
        <ChartCard
          title="Histórico diário de jobs"
          description="Volume total x status de sucesso e erro."
          tooltip="Evolução diária dos jobs executados."
          isLoading={isLoading && !metrics}
        >
          {jobHistory.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={jobHistory} margin={{ top: 8, left: 4, right: 4, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={successColor} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={successColor} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorDanger" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={dangerColor} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={dangerColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={surfaceBorder} strokeDasharray="4 4" />
                <XAxis
                  dataKey="date"
                  stroke={textMuted}
                  tickFormatter={(value) => dayFormatter.format(new Date(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis stroke={textMuted} tickLine={false} axisLine={false} />
                <RechartsTooltip
                  contentStyle={{
                    background: 'var(--iptv-surface-bg)',
                    border: `1px solid ${surfaceBorder}`,
                    borderRadius: '0.75rem',
                    boxShadow: '0 18px 40px -24px rgba(15, 23, 42, 0.35)',
                  }}
                  labelFormatter={(value) => formatFullDate(value)}
                />
                <Area type="monotone" dataKey="total" stroke={primaryColor} strokeWidth={2} fillOpacity={0.12} fill={primaryColor} />
                <Area type="monotone" dataKey="success" stroke={successColor} strokeWidth={2} fill="url(#colorSuccess)" />
                <Area type="monotone" dataKey="failed" stroke={dangerColor} strokeWidth={2} fill="url(#colorDanger)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="dashboard-card__empty">Nenhum histórico disponível.</div>
          )}
        </ChartCard>

        <ChartCard
          title="Tempo médio de importação"
          description="Comparativo diário em segundos."
          tooltip="Tempo médio gasto em cada job por dia."
          isLoading={isLoading && !metrics}
        >
          {durationHistory.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={durationHistory} margin={{ top: 8, left: 4, right: 4, bottom: 0 }}>
                <CartesianGrid stroke={surfaceBorder} strokeDasharray="4 4" />
                <XAxis
                  dataKey="date"
                  stroke={textMuted}
                  tickFormatter={(value) => dayFormatter.format(new Date(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis stroke={textMuted} tickLine={false} axisLine={false} />
                <RechartsTooltip
                  contentStyle={{
                    background: 'var(--iptv-surface-bg)',
                    border: `1px solid ${surfaceBorder}`,
                    borderRadius: '0.75rem',
                  }}
                  formatter={(value: number) => [`${Math.round(value)}s`, 'Tempo médio']}
                  labelFormatter={(value) => formatFullDate(value)}
                />
                <Line type="monotone" dataKey="averageSeconds" stroke={infoColor} strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="dashboard-card__empty">Nenhum dado de duração disponível.</div>
          )}
        </ChartCard>

        <ChartCard
          title="Streams importados"
          description="Filmes x séries por período."
          tooltip="Volume de conteúdo importado diariamente."
          isLoading={isLoading && !metrics}
        >
          {streamVolume.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={streamVolume} margin={{ top: 8, left: 4, right: 4, bottom: 0 }}>
                <CartesianGrid stroke={surfaceBorder} strokeDasharray="4 4" />
                <XAxis
                  dataKey="date"
                  stroke={textMuted}
                  tickFormatter={(value) => dayFormatter.format(new Date(value))}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis stroke={textMuted} tickLine={false} axisLine={false} />
                <RechartsTooltip
                  contentStyle={{
                    background: 'var(--iptv-surface-bg)',
                    border: `1px solid ${surfaceBorder}`,
                    borderRadius: '0.75rem',
                  }}
                  formatter={(value: number, key: string) => [numberFormatter.format(value), key === 'movies' ? 'Filmes' : 'Séries']}
                  labelFormatter={(value) => formatFullDate(value)}
                />
                <Bar dataKey="movies" stackId="a" fill={primaryColor} radius={[8, 8, 0, 0]} />
                <Bar dataKey="series" stackId="a" fill={successColor} radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="dashboard-card__empty">Sem dados de streams importados.</div>
          )}
        </ChartCard>

        <ChartCard
          title="Linha do tempo de jobs"
          description="Últimas execuções com status e duração."
          tooltip="Detalhamento das execuções mais recentes."
          isLoading={isLoading && !metrics}
        >
          <JobTimeline jobs={recentJobs} isLoading={isLoading && !metrics} />
        </ChartCard>

        <ChartCard
          title="Sincronizações por tenant"
          description="Status consolidado das últimas execuções."
          tooltip="Tenants monitorados com o horário da última sincronização."
          isLoading={isLoading && !metrics}
        >
          {tenants.length ? (
            <ul className="dashboard-tenant-list">
              {tenants.map((tenant) => (
                <li key={tenant.tenantId}>
                  <div className="dashboard-tenant-list__avatar" aria-hidden="true">
                    {tenant.tenantName
                      .split(' ')
                      .map((part) => part[0])
                      .join('')
                      .slice(0, 2)
                      .toUpperCase()}
                  </div>
                  <div className="dashboard-tenant-list__info">
                    <span className="dashboard-tenant-list__name">{tenant.tenantName}</span>
                    <span className="dashboard-tenant-list__date" title={formatFullDate(tenant.lastSyncAt)}>
                      {formatTenantRelative(tenant.lastSyncAt)}
                    </span>
                  </div>
                  <span className={`dashboard-tenant-list__status dashboard-tenant-list__status--${tenant.status}`}>
                    {statusLabels[tenant.status]}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="dashboard-card__empty">Nenhuma sincronização registrada.</div>
          )}
        </ChartCard>
      </div>
    </section>
  );
}

function useCssVariable(name: string, fallback: string, trigger: unknown): string {
  const [value, setValue] = useState(fallback);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const computed = window.getComputedStyle(document.body).getPropertyValue(name).trim();
    setValue(computed || fallback);
  }, [fallback, name, trigger]);

  return value;
}

function formatTenantRelative(dateInput: string | null | undefined) {
  if (!dateInput) {
    return 'sem dados';
  }

  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) {
    return 'sem dados';
  }

  const diffSeconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));

  if (diffSeconds < 60) {
    return `há ${diffSeconds}s`;
  }

  const diffMinutes = Math.round(diffSeconds / 60);
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

function formatFullDate(value: unknown) {
  if (!value) {
    return '';
  }

  const date = new Date(value as string | number | Date);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatTimeDistance(timestamp: number) {
  const diffSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));

  if (diffSeconds <= 1) {
    return 'agora mesmo';
  }

  if (diffSeconds < 60) {
    return `há ${diffSeconds}s`;
  }

  const diffMinutes = Math.floor(diffSeconds / 60);

  if (diffMinutes < 60) {
    return `há ${diffMinutes} min`;
  }

  const diffHours = Math.floor(diffMinutes / 60);

  if (diffHours < 24) {
    return `há ${diffHours} h`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `há ${diffDays} dia${diffDays > 1 ? 's' : ''}`;
}
