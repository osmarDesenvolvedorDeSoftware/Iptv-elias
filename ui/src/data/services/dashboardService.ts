import { get, isMockEnabled } from '../adapters/ApiAdapter';
import { MockAdapter } from '../adapters/MockAdapter';

export type DashboardJobStatus = 'success' | 'error' | 'running' | 'queued' | 'cancelled';

export interface JobStatusSummary {
  status: DashboardJobStatus;
  count: number;
}

export interface TenantSyncInfo {
  tenantId: string;
  tenantName: string;
  lastSyncAt: string | null;
  status: DashboardJobStatus;
  avatarUrl?: string | null;
}

export interface JobTrendPoint {
  date: string;
  total: number;
  success?: number;
  failed?: number;
  running?: number;
}

export interface DurationPoint {
  date: string;
  averageSeconds: number;
}

export interface StreamVolumePoint {
  date: string;
  movies: number;
  series: number;
}

export interface RecentJobSummary {
  id: string;
  name: string;
  status: DashboardJobStatus;
  startedAt: string;
  finishedAt?: string;
  tenantName?: string;
  durationSeconds?: number;
  type?: string;
  message?: string;
}

export interface DashboardMetrics {
  tenantCount: number;
  totalJobs: number;
  statusSummary: JobStatusSummary[];
  tenants: TenantSyncInfo[];
  jobHistory: JobTrendPoint[];
  averageImportDuration: DurationPoint[];
  streamVolume: StreamVolumePoint[];
  recentJobs: RecentJobSummary[];
  lastUpdatedAt: string;
}

interface DashboardApiResponse {
  tenantCount?: number;
  tenants?: unknown;
  totals?: { tenants?: unknown; jobs?: unknown };
  totalJobs?: number;
  jobs?: {
    total?: unknown;
    statusSummary?: unknown;
    statuses?: unknown;
    recent?: unknown;
    history?: unknown;
    averageDuration?: unknown;
    volume?: unknown;
    lastUpdatedAt?: unknown;
  };
  statusSummary?: unknown;
  tenantsSync?: unknown;
  recentJobs?: unknown;
  jobHistory?: unknown;
  averageImportDuration?: unknown;
  streamVolume?: unknown;
  lastUpdatedAt?: unknown;
}

const DASHBOARD_ENDPOINT = '/api/jobs';

export async function fetchDashboardMetrics(signal?: AbortSignal): Promise<DashboardMetrics> {
  if (isMockEnabled) {
    const mock = await MockAdapter.fetch<DashboardApiResponse>('dashboard.metrics.json');
    return normalizeDashboardResponse(mock);
  }

  const response = await get<DashboardApiResponse>(DASHBOARD_ENDPOINT, { signal });
  return normalizeDashboardResponse(response);
}

function normalizeDashboardResponse(payload: DashboardApiResponse | null | undefined): DashboardMetrics {
  const tenantCount = determineTenantCount(payload);
  const totalJobs = determineTotalJobs(payload);

  const statusSummary = normalizeStatusSummary(payload);
  const tenants = normalizeTenants(payload);
  const jobHistory = normalizeJobHistory(payload);
  const averageImportDuration = normalizeDurations(payload);
  const streamVolume = normalizeStreamVolume(payload);
  const recentJobs = normalizeRecentJobs(payload);

  const lastUpdatedAt = normalizeDate(
    payload?.lastUpdatedAt ?? payload?.jobs?.lastUpdatedAt ?? recentJobs[0]?.startedAt ?? new Date().toISOString(),
  );

  return {
    tenantCount,
    totalJobs,
    statusSummary,
    tenants,
    jobHistory,
    averageImportDuration,
    streamVolume,
    recentJobs,
    lastUpdatedAt,
  };
}

function determineTenantCount(payload: DashboardApiResponse | null | undefined): number {
  if (!payload) {
    return 0;
  }

  if (typeof payload.tenantCount === 'number') {
    return payload.tenantCount;
  }

  if (typeof payload.totals?.tenants === 'number') {
    return payload.totals.tenants;
  }

  if (Array.isArray(payload.tenants)) {
    return payload.tenants.length;
  }

  if (Array.isArray(payload.tenantsSync)) {
    return payload.tenantsSync.length;
  }

  if (typeof payload.totalJobs === 'number' && typeof payload.jobs?.total === 'number') {
    return payload.totalJobs > 0 ? Math.max(1, Math.floor(payload.totalJobs / Math.max(payload.jobs.total, 1))) : 0;
  }

  return 0;
}

function determineTotalJobs(payload: DashboardApiResponse | null | undefined): number {
  if (!payload) {
    return 0;
  }

  if (typeof payload.totalJobs === 'number') {
    return payload.totalJobs;
  }

  if (typeof payload.totals?.jobs === 'number') {
    return payload.totals.jobs;
  }

  if (typeof payload.jobs?.total === 'number') {
    return payload.jobs.total;
  }

  if (Array.isArray(payload.jobHistory)) {
    return payload.jobHistory.reduce((acc, item) => acc + (typeof item?.total === 'number' ? item.total : 0), 0);
  }

  if (Array.isArray(payload.jobs?.history)) {
    return payload.jobs.history.reduce((acc, item) => acc + (typeof item?.total === 'number' ? item.total : 0), 0);
  }

  return 0;
}

function normalizeStatusSummary(payload: DashboardApiResponse | null | undefined): JobStatusSummary[] {
  const summary: JobStatusSummary[] = [];
  const append = (status: DashboardJobStatus, count: number | undefined) => {
    if (typeof count === 'number' && Number.isFinite(count)) {
      summary.push({ status, count });
    }
  };

  const fromArray = (value: unknown) => {
    if (!Array.isArray(value)) {
      return false;
    }

    value.forEach((item) => {
      if (item && typeof item === 'object') {
        const status = normalizeStatus((item as Record<string, unknown>).status);
        const count = Number((item as Record<string, unknown>).count);
        if (Number.isFinite(count)) {
          append(status, count);
        }
      }
    });

    return summary.length > 0;
  };

  const fromRecord = (value: unknown) => {
    if (!value || typeof value !== 'object') {
      return false;
    }

    Object.entries(value as Record<string, unknown>).forEach(([statusKey, countValue]) => {
      const status = normalizeStatus(statusKey);
      const count = Number(countValue);
      if (Number.isFinite(count)) {
        append(status, count);
      }
    });

    return summary.length > 0;
  };

  if (fromArray(payload?.statusSummary)) {
    return fillStatusSummary(summary);
  }

  if (fromArray(payload?.jobs?.statusSummary)) {
    return fillStatusSummary(summary);
  }

  if (fromArray(payload?.jobs?.recent)) {
    const counts = payload?.jobs?.recent as unknown[];
    const map = new Map<DashboardJobStatus, number>();
    counts.forEach((item) => {
      if (item && typeof item === 'object') {
        const status = normalizeStatus((item as Record<string, unknown>).status);
        map.set(status, (map.get(status) ?? 0) + 1);
      }
    });
    map.forEach((count, status) => append(status, count));
    return fillStatusSummary(summary);
  }

  if (fromRecord(payload?.jobs?.statuses)) {
    return fillStatusSummary(summary);
  }

  if (fromRecord(payload?.jobs?.statusSummary)) {
    return fillStatusSummary(summary);
  }

  if (fromRecord(payload?.statusSummary)) {
    return fillStatusSummary(summary);
  }

  return fillStatusSummary(summary);
}

const SUMMARY_STATUSES: DashboardJobStatus[] = ['success', 'error', 'running'];

function fillStatusSummary(summary: JobStatusSummary[]): JobStatusSummary[] {
  const map = new Map<DashboardJobStatus, number>();
  summary.forEach((item) => {
    map.set(item.status, (map.get(item.status) ?? 0) + item.count);
  });

  SUMMARY_STATUSES.forEach((status) => {
    if (!map.has(status)) {
      map.set(status, 0);
    }
  });

  return SUMMARY_STATUSES.map((status) => ({ status, count: map.get(status) ?? 0 }));
}

function normalizeTenants(payload: DashboardApiResponse | null | undefined): TenantSyncInfo[] {
  const source = Array.isArray(payload?.tenants)
    ? payload?.tenants
    : Array.isArray(payload?.tenantsSync)
    ? payload?.tenantsSync
    : [];

  return source
    .map((item) => normalizeTenant(item))
    .filter((item, index, array) => Boolean(item) && array.findIndex((entry) => entry?.tenantId === item?.tenantId) === index)
    .map((item) => item!)
    .sort((a, b) => {
      const timeA = a.lastSyncAt ? new Date(a.lastSyncAt).getTime() : 0;
      const timeB = b.lastSyncAt ? new Date(b.lastSyncAt).getTime() : 0;
      return timeB - timeA;
    });
}

function normalizeTenant(value: unknown): TenantSyncInfo | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const record = value as Record<string, unknown>;
  const tenantId = String(record.tenantId ?? record.id ?? '');

  if (!tenantId) {
    return null;
  }

  const tenantName = String(record.tenantName ?? record.name ?? tenantId);
  const lastSyncAt = normalizeDate(record.lastSyncAt ?? record.syncedAt ?? record.updatedAt ?? null);
  const status = normalizeStatus(record.status);
  const avatarUrl = typeof record.avatarUrl === 'string' ? record.avatarUrl : undefined;

  return {
    tenantId,
    tenantName,
    lastSyncAt,
    status,
    avatarUrl: avatarUrl ?? null,
  };
}

function normalizeJobHistory(payload: DashboardApiResponse | null | undefined): JobTrendPoint[] {
  const source = Array.isArray(payload?.jobHistory)
    ? payload?.jobHistory
    : Array.isArray(payload?.jobs?.history)
    ? payload?.jobs?.history
    : [];

  return source
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }

      const record = item as Record<string, unknown>;
      const date = normalizeDate(record.date ?? record.day ?? record.label ?? new Date().toISOString());
      const total = Number(record.total ?? record.count ?? 0);
      const success = Number(record.success ?? record.succeeded ?? record.finished ?? 0);
      const failed = Number(record.failed ?? record.errors ?? record.errored ?? 0);
      const running = Number(record.running ?? record.inProgress ?? record.progress ?? 0);

      return {
        date,
        total: Number.isFinite(total) ? total : 0,
        success: Number.isFinite(success) ? success : undefined,
        failed: Number.isFinite(failed) ? failed : undefined,
        running: Number.isFinite(running) ? running : undefined,
      } satisfies JobTrendPoint;
    })
    .filter((item): item is JobTrendPoint => Boolean(item));
}

function normalizeDurations(payload: DashboardApiResponse | null | undefined): DurationPoint[] {
  const source = Array.isArray(payload?.averageImportDuration)
    ? payload?.averageImportDuration
    : Array.isArray(payload?.jobs?.averageDuration)
    ? payload?.jobs?.averageDuration
    : [];

  return source
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }

      const record = item as Record<string, unknown>;
      const date = normalizeDate(record.date ?? record.day ?? record.label ?? new Date().toISOString());
      const averageSeconds = Number(record.averageSeconds ?? record.seconds ?? record.value ?? 0);

      return {
        date,
        averageSeconds: Number.isFinite(averageSeconds) ? averageSeconds : 0,
      } satisfies DurationPoint;
    })
    .filter((item): item is DurationPoint => Boolean(item));
}

function normalizeStreamVolume(payload: DashboardApiResponse | null | undefined): StreamVolumePoint[] {
  const source = Array.isArray(payload?.streamVolume)
    ? payload?.streamVolume
    : Array.isArray(payload?.jobs?.volume)
    ? payload?.jobs?.volume
    : [];

  return source
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }

      const record = item as Record<string, unknown>;
      const date = normalizeDate(record.date ?? record.day ?? record.label ?? new Date().toISOString());
      const movies = Number(record.movies ?? record.filmes ?? record.moviesCount ?? 0);
      const series = Number(record.series ?? record.seriesCount ?? record.shows ?? 0);

      return {
        date,
        movies: Number.isFinite(movies) ? movies : 0,
        series: Number.isFinite(series) ? series : 0,
      } satisfies StreamVolumePoint;
    })
    .filter((item): item is StreamVolumePoint => Boolean(item));
}

function normalizeRecentJobs(payload: DashboardApiResponse | null | undefined): RecentJobSummary[] {
  const source = Array.isArray(payload?.recentJobs)
    ? payload?.recentJobs
    : Array.isArray(payload?.jobs?.recent)
    ? payload?.jobs?.recent
    : [];

  return source
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }

      const record = item as Record<string, unknown>;
      const idRaw = record.id ?? record.jobId ?? record.uuid ?? record.reference ?? record.name;
      if (idRaw === undefined || idRaw === null) {
        return null;
      }

      const id = String(idRaw);
      const name = String(record.name ?? record.title ?? `Job ${id}`);
      const status = normalizeStatus(record.status);
      const startedAt = normalizeDate(record.startedAt ?? record.startTime ?? record.createdAt ?? new Date().toISOString());
      const finishedAt = normalizeDate(record.finishedAt ?? record.endTime ?? record.completedAt ?? null);
      const tenantName = typeof record.tenantName === 'string' ? record.tenantName : undefined;
      const durationValue = Number(record.durationSeconds ?? record.duration ?? record.elapsedSeconds ?? 0);
      const message = typeof record.message === 'string' ? record.message : undefined;
      const type = typeof record.type === 'string' ? record.type : undefined;

      return {
        id,
        name,
        status,
        startedAt,
        finishedAt,
        tenantName,
        durationSeconds: Number.isFinite(durationValue) ? durationValue : undefined,
        message,
        type,
      } satisfies RecentJobSummary;
    })
    .filter((item): item is RecentJobSummary => Boolean(item));
}

function normalizeStatus(value: unknown): DashboardJobStatus {
  const raw = String(value ?? '').toLowerCase();

  if (['success', 'succeeded', 'completed', 'finished', 'ok'].includes(raw)) {
    return 'success';
  }

  if (['error', 'failed', 'failure'].includes(raw)) {
    return 'error';
  }

  if (['running', 'processing', 'in_progress', 'active'].includes(raw)) {
    return 'running';
  }

  if (['cancelled', 'canceled', 'aborted'].includes(raw)) {
    return 'cancelled';
  }

  return 'queued';
}

function normalizeDate(value: unknown): string | null {
  if (!value) {
    return null;
  }

  const date = new Date(value as string | number | Date);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date.toISOString();
}
