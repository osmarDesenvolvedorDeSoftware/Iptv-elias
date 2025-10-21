import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { List, type ListImperativeAPI, type RowComponentProps } from 'react-window';

import type { JobLogEntry } from '../../data/types';

export type LogFilter = 'all' | 'warnings' | 'errors';

function resolveLevel(log: JobLogEntry): 'info' | 'warning' | 'error' {
  const raw = String(log.level ?? log.severity ?? log.kind ?? '').toLowerCase();
  if (raw.includes('error') || raw.includes('exception') || raw.includes('fail')) {
    return 'error';
  }
  if (raw.includes('warn') || raw.includes('normalizationerror')) {
    return 'warning';
  }
  return 'info';
}

function formatTime(value?: string): string {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function buildMessage(log: JobLogEntry): string {
  if (typeof log.message === 'string' && log.message.trim().length > 0) {
    return log.message;
  }
  const clone = { ...log } as Record<string, unknown>;
  delete clone.id;
  delete clone.createdAt;
  delete clone.message;
  return JSON.stringify(clone, null, 2);
}

interface ImportLogsViewerProps {
  logs: JobLogEntry[];
  filter: LogFilter;
  onFilterChange: (filter: LogFilter) => void;
  loading: boolean;
  error: string | null;
  isStreaming: boolean;
  onRetry?: () => void;
}

const FILTERS: Array<{ value: LogFilter; label: string }> = [
  { value: 'all', label: 'Todos' },
  { value: 'errors', label: 'Erros' },
  { value: 'warnings', label: 'Warnings' },
];

const ESTIMATED_LINE_HEIGHT = 18;
const BASE_ITEM_HEIGHT = 88;

export function ImportLogsViewer({ logs, filter, onFilterChange, loading, error, isStreaming, onRetry }: ImportLogsViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<ListImperativeAPI | null>(null);
  const measureCache = useRef(new Map<number, number>());
  const [dimensions, setDimensions] = useState({ width: 0, height: 320 });
  const [autoScroll, setAutoScroll] = useState(true);
  const rowProps = useMemo(() => ({} as Record<string, never>), []);

  const filteredLogs = useMemo(() => {
    if (filter === 'all') {
      return logs;
    }
    return logs.filter((entry) => {
      const level = resolveLevel(entry);
      if (filter === 'errors') {
        return level === 'error';
      }
      return level === 'warning';
    });
  }, [filter, logs]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(element);
    setDimensions({ width: element.clientWidth, height: element.clientHeight });

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    measureCache.current.clear();
    if (autoScroll && filteredLogs.length > 0) {
      listRef.current?.scrollToRow({ index: filteredLogs.length - 1, align: 'end' });
    }
  }, [autoScroll, filteredLogs]);

  const getRowHeight = useCallback(
    (index: number, _rowProps?: Record<string, never>) => {
      const entry = filteredLogs[index];
      if (!entry) {
        return BASE_ITEM_HEIGHT;
      }
      const cached = measureCache.current.get(entry.id);
      if (cached) {
        return cached;
      }
      const message = buildMessage(entry);
      const approxLines = Math.ceil(Math.max(message.length, 40) / 80);
      const height = BASE_ITEM_HEIGHT + approxLines * ESTIMATED_LINE_HEIGHT;
      measureCache.current.set(entry.id, height);
      return height;
    },
    [filteredLogs],
  );

  const renderRow = useCallback(
    ({ index, style, ariaAttributes }: RowComponentProps<Record<string, never>>) => {
      const log = filteredLogs[index];
      if (!log) {
        return null;
      }
      const level = resolveLevel(log);
      const message = buildMessage(log);
      const createdAt = formatTime(log.createdAt);
      const levelClass =
        level === 'error'
          ? 'border-danger-subtle bg-danger-subtle text-body'
          : level === 'warning'
          ? 'border-warning-subtle bg-warning-subtle text-body'
          : 'border-secondary-subtle';

      return (
        <div style={{ ...style, padding: '0 0.5rem' }} {...ariaAttributes}>
          <article className={`border rounded-3 p-3 mb-2 ${levelClass}`}>
            <header className="d-flex justify-content-between align-items-start mb-2">
              <div className="d-flex flex-column">
                <span className="badge bg-secondary-subtle text-secondary small">{createdAt}</span>
                {log.kind ? <span className="small text-muted">{log.kind}</span> : null}
              </div>
              <div className="text-muted small">#{log.id}</div>
            </header>
            <p className="mb-2 small fw-semibold text-break">{message.split('\n')[0]}</p>
            {message.includes('\n') ? (
              <pre className="mb-0 small bg-body-tertiary p-2 rounded text-break" style={{ whiteSpace: 'pre-wrap' }}>
                {message}
              </pre>
            ) : null}
            {log.domain || log.source ? (
              <footer className="mt-2 small text-muted d-flex gap-3">
                {log.domain ? <span>Domínio: {String(log.domain)}</span> : null}
                {log.source ? <span>Origem: {String(log.source)}</span> : null}
              </footer>
            ) : null}
          </article>
        </div>
      );
    },
    [filteredLogs],
  );

  useEffect(() => {
    const element = listRef.current?.element ?? null;
    if (!element) {
      return;
    }
    const handleScroll = () => {
      const nearBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 80;
      setAutoScroll(nearBottom);
    };
    element.addEventListener('scroll', handleScroll);
    handleScroll();
    return () => element.removeEventListener('scroll', handleScroll);
  }, [filteredLogs.length]);

  return (
    <div className="card shadow-sm">
      <div className="card-header d-flex flex-column flex-lg-row justify-content-between gap-2 align-items-lg-center">
        <span className="fw-semibold">Logs em Tempo Real</span>
        <div className="btn-group btn-group-sm" role="group" aria-label="Filtro de logs">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`btn btn-outline-secondary ${filter === item.value ? 'active' : ''}`}
              onClick={() => onFilterChange(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card-body d-flex flex-column gap-3">
        {error ? (
          <div className="alert alert-danger d-flex justify-content-between align-items-start" role="alert">
            <span>{error}</span>
            {onRetry ? (
              <button type="button" className="btn btn-sm btn-light" onClick={onRetry}>
                Tentar novamente
              </button>
            ) : null}
          </div>
        ) : null}

        <div ref={containerRef} className="border rounded-3 bg-body-tertiary" style={{ height: '24rem', overflow: 'hidden' }}>
          {filteredLogs.length === 0 ? (
            <div className="h-100 d-flex flex-column justify-content-center align-items-center text-muted gap-2">
              {loading ? (
                <span className="spinner-border spinner-border-sm" aria-hidden="true" />
              ) : (
                <span aria-hidden="true">ℹ️</span>
              )}
              <p className="mb-0">Nenhum log disponível para o filtro selecionado.</p>
            </div>
          ) : (
            <List<Record<string, never>>
              style={{ height: Math.max(dimensions.height, 160), width: Math.max(dimensions.width, 320) }}
              rowCount={filteredLogs.length}
              rowHeight={getRowHeight}
              rowComponent={renderRow}
              rowProps={rowProps}
              listRef={listRef}
              overscanCount={4}
            />
          )}
        </div>

        <div className="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2 text-muted small">
          <div className="d-flex align-items-center gap-2">
            {isStreaming ? <span aria-hidden="true">🟢</span> : <span aria-hidden="true">🔄</span>}
            <span>{isStreaming ? 'Recebendo logs em tempo real.' : 'Atualização periódica ativa.'}</span>
          </div>
          <div className="d-flex align-items-center gap-3">
            {loading ? (
              <div className="d-flex align-items-center gap-2">
                <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                <span>Carregando…</span>
              </div>
            ) : null}
            {!autoScroll && filteredLogs.length > 0 ? (
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={() => {
                  setAutoScroll(true);
                  listRef.current?.scrollToRow({ index: filteredLogs.length - 1, align: 'end' });
                }}
              >
                Retomar auto rolagem
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
