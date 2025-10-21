import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import {
  getHistory as fetchHistory,
  getJob as fetchJob,
  getJobLogs as fetchJobLogs,
  openJobLogStream,
  startJob as startJobRequest,
  type HistoryQuery,
  type ImportJobAction,
  type JobLogsParams,
} from '../data/services/importService';
import type {
  ImportJobStatus,
  JobDetail,
  JobLogEntry,
  JobLogsResponse,
  LogListResponse,
} from '../data/types';
import { useAuth } from '../providers/AuthProvider';

const LAST_JOB_STORAGE_KEY = 'iptv:lastImportJobId';
const MAX_LOG_ITEMS = 2000;

function persistJobId(jobId: number | null) {
  if (typeof window === 'undefined') {
    return;
  }
  if (jobId === null) {
    window.localStorage.removeItem(LAST_JOB_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(LAST_JOB_STORAGE_KEY, String(jobId));
}

export interface JobProgressSnapshot {
  inserted: number;
  updated: number;
  ignored: number;
  errors: number;
  durationSec?: number;
  etaSec?: number;
  progress?: number;
  startedAt?: string;
  finishedAt?: string;
}

export interface UseImportJobsResult {
  currentJob: JobDetail | null;
  status: ImportJobStatus | 'idle';
  progress: JobProgressSnapshot;
  jobLoading: boolean;
  jobError: string | null;
  logs: JobLogEntry[];
  logsLoading: boolean;
  logsError: string | null;
  isStreaming: boolean;
  startJob: (action: ImportJobAction) => Promise<JobDetail>;
  loadJob: (jobId: number) => Promise<JobDetail>;
  clearJob: () => void;
  getLogs: (jobId: number, params?: JobLogsParams) => Promise<JobLogsResponse>;
  getHistory: (filters?: HistoryQuery) => Promise<LogListResponse>;
}

export function useImportJobs(): UseImportJobsResult {
  const { accessToken, tenantId } = useAuth();
  const [currentJob, setCurrentJob] = useState<JobDetail | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [logs, setLogs] = useState<JobLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const logCursorRef = useRef<number | null>(null);
  const syntheticIdRef = useRef(-1);

  const normalizePayload = useCallback(
    (payload: unknown): JobLogEntry[] => {
      const entries: JobLogEntry[] = [];

      const append = (value: unknown) => {
        if (Array.isArray(value)) {
          value.forEach(append);
          return;
        }

        if (value === null || value === undefined) {
          return;
        }

        if (typeof value === 'string') {
          if (!value) {
            return;
          }
          syntheticIdRef.current -= 1;
          entries.push({
            id: syntheticIdRef.current,
            createdAt: new Date().toISOString(),
            message: value,
          });
          return;
        }

        if (typeof value === 'object') {
          const source = value as Record<string, unknown>;
          let idValue = Number(source.id);
          if (!Number.isFinite(idValue)) {
            syntheticIdRef.current -= 1;
            idValue = syntheticIdRef.current;
          }
          const createdAtValue =
            typeof source.createdAt === 'string' ? (source.createdAt as string) : new Date().toISOString();

          const normalized: JobLogEntry = {
            ...(source as JobLogEntry),
            id: idValue,
            createdAt: createdAtValue,
          };

          entries.push(normalized);
        }
      };

      append(payload);
      return entries;
    },
    [],
  );

  const appendLogs = useCallback((items: JobLogEntry[], reset = false) => {
    if (reset) {
      if (items.length === 0) {
        setLogs([]);
        return;
      }
      const sliced = items.length > MAX_LOG_ITEMS ? items.slice(items.length - MAX_LOG_ITEMS) : [...items];
      setLogs(sliced);
      return;
    }

    if (items.length === 0) {
      return;
    }

    setLogs((prev) => {
      const existing = new Set(prev.map((item) => item.id));
      const merged = [...prev];

      for (const entry of items) {
        if (existing.has(entry.id)) {
          continue;
        }
        merged.push(entry);
        existing.add(entry.id);
      }

      merged.sort((a, b) => a.id - b.id);
      if (merged.length > MAX_LOG_ITEMS) {
        return merged.slice(merged.length - MAX_LOG_ITEMS);
      }
      return merged;
    });
  }, []);

  const loadJob = useCallback(async (jobId: number) => {
    setJobLoading(true);
    setJobError(null);
    try {
      const detail = await fetchJob(jobId);
      setCurrentJob(detail);
      persistJobId(detail.id);
      return detail;
    } catch (error) {
      const apiError = error as ApiError;
      setJobError(apiError?.message ?? 'Não foi possível carregar informações do job.');
      setCurrentJob((prev) => (prev?.id === jobId ? null : prev));
      persistJobId(null);
      throw error;
    } finally {
      setJobLoading(false);
    }
  }, []);

  const startJob = useCallback(
    async (action: ImportJobAction) => {
      setJobError(null);
      try {
        const response = await startJobRequest(action);
        return await loadJob(response.jobId);
      } catch (error) {
        const apiError = error as ApiError;
        setJobError(apiError?.message ?? 'Não foi possível iniciar a importação.');
        throw error;
      }
    },
    [loadJob],
  );

  const clearJob = useCallback(() => {
    setCurrentJob(null);
    setLogs([]);
    setLogsError(null);
    setJobError(null);
    logCursorRef.current = null;
    syntheticIdRef.current = -1;
    persistJobId(null);
  }, []);

  const getLogs = useCallback(
    (jobId: number, params: JobLogsParams = {}) => {
      return fetchJobLogs(jobId, params);
    },
    [],
  );

  const getHistory = useCallback((filters: HistoryQuery = {}) => fetchHistory(filters), []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const stored = window.localStorage.getItem(LAST_JOB_STORAGE_KEY);
    if (!stored) {
      return;
    }

    const parsed = Number(stored);
    if (Number.isNaN(parsed)) {
      persistJobId(null);
      return;
    }

    void loadJob(parsed).catch(() => {
      persistJobId(null);
    });
  }, [loadJob]);

  useEffect(() => {
    const jobId = currentJob?.id;
    if (!jobId) {
      setLogs([]);
      setLogsError(null);
      setLogsLoading(false);
      logCursorRef.current = null;
      return;
    }

    let active = true;
    setLogsLoading(true);
    setLogsError(null);
    logCursorRef.current = null;

    fetchJobLogs(jobId, { limit: 200 })
      .then((response) => {
        if (!active) {
          return;
        }
        const normalized = normalizePayload(response.items);
        appendLogs(normalized, true);
        if (typeof response.nextAfter === 'number') {
          logCursorRef.current = response.nextAfter;
        } else if (normalized.length > 0) {
          logCursorRef.current = normalized[normalized.length - 1].id;
        } else {
          logCursorRef.current = null;
        }
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        const apiError = error as ApiError;
        setLogsError(apiError?.message ?? 'Não foi possível carregar os logs do job.');
        setLogs([]);
        logCursorRef.current = null;
      })
      .finally(() => {
        if (active) {
          setLogsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [appendLogs, currentJob?.id, normalizePayload]);

  useEffect(() => {
    const jobId = currentJob?.id;
    if (!jobId) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setIsStreaming(false);
      return;
    }

    const status = currentJob?.status;
    const shouldStream = status === 'running' || status === 'queued';

    if (!shouldStream) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setIsStreaming(false);
      return;
    }

    let active = true;

    const startPolling = () => {
      if (!active) {
        return;
      }
      setIsStreaming(false);
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
      }

      const executePoll = async () => {
        try {
          const response = await fetchJobLogs(
            jobId,
            logCursorRef.current ? { after: logCursorRef.current } : {},
          );
          if (!active) {
            return;
          }
          if (response.items.length > 0) {
            const normalized = normalizePayload(response.items);
            appendLogs(normalized);
            setLogsError(null);
            if (typeof response.nextAfter === 'number') {
              logCursorRef.current = response.nextAfter;
            } else if (normalized.length > 0) {
              logCursorRef.current = normalized[normalized.length - 1].id;
            }
          }
        } catch (error) {
          if (!active) {
            return;
          }
          const apiError = error as ApiError;
          setLogsError(apiError?.message ?? 'Falha ao atualizar logs do job.');
        }
      };

      pollTimerRef.current = window.setInterval(executePoll, 4000);
      void executePoll();
    };

    const startStream = () => {
      if (!active || !accessToken) {
        startPolling();
        return;
      }

      try {
        const eventSource = openJobLogStream(jobId, {
          token: accessToken,
          tenantId,
          lastEventId: logCursorRef.current ?? null,
        });

        eventSourceRef.current = eventSource;
        setIsStreaming(true);

        eventSource.onmessage = (event) => {
          if (!active) {
            return;
          }
          try {
            const parsed = JSON.parse(event.data) as unknown;
            const normalized = normalizePayload(parsed);
            if (normalized.length > 0) {
              appendLogs(normalized);
              setLogsError(null);
              logCursorRef.current = normalized[normalized.length - 1].id;
            }
          } catch (err) {
            const normalized = normalizePayload(event.data);
            if (normalized.length > 0) {
              appendLogs(normalized);
              logCursorRef.current = normalized[normalized.length - 1].id;
            }
          }
        };

        eventSource.onerror = () => {
          if (!active) {
            return;
          }
          setIsStreaming(false);
          eventSource.close();
          eventSourceRef.current = null;
          startPolling();
        };
      } catch (error) {
        console.warn('SSE indisponível, usando fallback de polling.', error);
        setIsStreaming(false);
        startPolling();
      }
    };

    startStream();

    return () => {
      active = false;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setIsStreaming(false);
    };
  }, [accessToken, appendLogs, currentJob?.id, currentJob?.status, normalizePayload, tenantId]);

  useEffect(() => {
    const jobId = currentJob?.id;
    if (!jobId) {
      return;
    }

    if (currentJob?.status !== 'running' && currentJob?.status !== 'queued') {
      return;
    }

    let active = true;

    const interval = window.setInterval(() => {
      fetchJob(jobId)
        .then((detail) => {
          if (!active) {
            return;
          }
          setCurrentJob(detail);
        })
        .catch((error) => {
          if (!active) {
            return;
          }
          const apiError = error as ApiError;
          setJobError((prev) => prev ?? apiError?.message ?? 'Não foi possível atualizar status do job.');
        });
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [currentJob?.id, currentJob?.status]);

  const progress = useMemo<JobProgressSnapshot>(() => {
    if (!currentJob) {
      return { inserted: 0, updated: 0, ignored: 0, errors: 0 };
    }

    return {
      inserted: currentJob.inserted ?? 0,
      updated: currentJob.updated ?? 0,
      ignored: currentJob.ignored ?? 0,
      errors: currentJob.errors ?? 0,
      durationSec: currentJob.durationSec ?? undefined,
      etaSec: currentJob.etaSec ?? undefined,
      progress: currentJob.progress ?? undefined,
      startedAt: currentJob.startedAt,
      finishedAt: currentJob.finishedAt,
    };
  }, [currentJob]);

  const status: ImportJobStatus | 'idle' = currentJob?.status ?? 'idle';

  return {
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
    clearJob,
    getLogs,
    getHistory,
  };
}
