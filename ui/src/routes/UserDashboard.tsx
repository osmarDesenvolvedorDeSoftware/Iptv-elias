import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { fetchConfig, saveConfig, testConfig } from '../data/services/accountService';
import { getImports, runImport } from '../data/services/importerService';
import { ImportJobHistoryItem, ImportType, UserConfigData } from '../data/types';
import { useToast } from '../providers/ToastProvider';

type JobSummary = Record<ImportType, ImportJobHistoryItem | null>;

export default function UserDashboard() {
  const { push } = useToast();
  const [config, setConfig] = useState<UserConfigData | null>(null);
  const [formState, setFormState] = useState({
    domain: '',
    port: '',
    username: '',
    password: '',
    active: true,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobSummary>({ filmes: null, series: null });
  const [syncing, setSyncing] = useState<ImportType | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hasExistingPassword = config?.hasPassword && !formState.password;

  const lastSyncLabel = useMemo(() => {
    if (!config?.lastSync) {
      return 'Nenhuma sincronização registrada.';
    }

    try {
      const date = new Date(config.lastSync);
      return `Última sincronização: ${date.toLocaleString('pt-BR')}`;
    } catch (err) {
      return 'Última sincronização disponível.';
    }
  }, [config?.lastSync]);

  const loadImports = useCallback(async () => {
    try {
      const [movies, series] = await Promise.all([getImports('filmes'), getImports('series')]);
      setJobs({
        filmes: movies.items[0] ?? null,
        series: series.items[0] ?? null,
      });
    } catch (err) {
      console.warn('Falha ao carregar histórico de importações', err);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetchConfig();
        if (cancelled) {
          return;
        }
        setConfig(response);
        setFormState({
          domain: response.domain ?? '',
          port: response.port ? String(response.port) : '',
          username: response.username ?? '',
          password: '',
          active: response.active,
        });
        await loadImports();
      } catch (err) {
        if (!cancelled) {
          const apiError = err as ApiError;
          setError(apiError?.message ?? 'Não foi possível carregar a configuração.');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [loadImports]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSaving) {
      return;
    }

    setIsSaving(true);
    setError(null);

    const trimmedPort = formState.port.trim();
    const payload: Partial<UserConfigData> & { password?: string | null } = {
      domain: formState.domain.trim() || null,
      port: null,
      username: formState.username.trim() || null,
      active: formState.active,
    };

    if (trimmedPort) {
      const numericPort = Number(trimmedPort);
      if (Number.isNaN(numericPort)) {
        setError('Porta inválida.');
        setIsSaving(false);
        return;
      }
      payload.port = numericPort;
    }

    if (formState.password) {
      payload.password = formState.password;
    }

    try {
      const response = await saveConfig(payload);
      setConfig(response);
      setFormState((prev) => ({ ...prev, password: '' }));
      push({ type: 'success', message: 'Configuração salva com sucesso.' });
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível salvar a configuração.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTest() {
    if (isTesting) {
      return;
    }

    setIsTesting(true);
    setTestMessage(null);
    setError(null);

    try {
      const response = await testConfig();
      setTestMessage(response.message);
      push({ type: 'success', message: 'Conexão validada com sucesso.' });
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível testar a conexão.');
    } finally {
      setIsTesting(false);
    }
  }

  async function handleSync(type: ImportType) {
    if (syncing) {
      return;
    }

    setSyncing(type);
    setError(null);
    try {
      await runImport(type);
      push({ type: 'info', message: `Sincronização de ${type} iniciada.` });
      await loadImports();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível iniciar a sincronização.');
    } finally {
      setSyncing(null);
    }
  }

  return (
    <section className="dashboard dashboard--user">
      <header className="dashboard__header">
        <div>
          <h1 className="dashboard__title">Configuração da conta</h1>
          <p className="dashboard__subtitle">Cadastre os dados da sua conta IPTV e acompanhe as sincronizações.</p>
        </div>
        <span className="dashboard__timestamp" aria-live="polite">
          {lastSyncLabel}
        </span>
      </header>

      {error ? (
        <div className="dashboard__alert" role="alert">
          {error}
        </div>
      ) : null}

      <form className="card p-4 mb-4" onSubmit={handleSubmit}>
        <div className="row g-3">
          <div className="col-md-6">
            <label className="form-label" htmlFor="domain">
              Domínio ou IP
            </label>
            <input
              id="domain"
              name="domain"
              type="text"
              className="form-control"
              placeholder="ex: servidor.iptv.com"
              value={formState.domain}
              onChange={(event) => setFormState((prev) => ({ ...prev, domain: event.target.value }))}
              disabled={isLoading || isSaving}
              required
            />
          </div>

          <div className="col-md-2">
            <label className="form-label" htmlFor="port">
              Porta
            </label>
            <input
              id="port"
              name="port"
              type="number"
              min={0}
              max={65535}
              className="form-control"
              placeholder="80"
              value={formState.port}
              onChange={(event) => setFormState((prev) => ({ ...prev, port: event.target.value }))}
              disabled={isLoading || isSaving}
            />
          </div>

          <div className="col-md-4">
            <label className="form-label" htmlFor="username">
              Usuário IPTV
            </label>
            <input
              id="username"
              name="username"
              type="text"
              className="form-control"
              placeholder="usuario"
              value={formState.username}
              onChange={(event) => setFormState((prev) => ({ ...prev, username: event.target.value }))}
              disabled={isLoading || isSaving}
              required
            />
          </div>

          <div className="col-md-6">
            <label className="form-label" htmlFor="password">
              Senha IPTV
            </label>
            <input
              id="password"
              name="password"
              type="password"
              className="form-control"
              placeholder={hasExistingPassword ? 'Manter senha atual' : 'Digite a senha fornecida pela operadora'}
              value={formState.password}
              onChange={(event) => setFormState((prev) => ({ ...prev, password: event.target.value }))}
              disabled={isLoading || isSaving}
              minLength={4}
            />
          </div>

          <div className="col-md-6 d-flex align-items-end">
            <div className="form-check">
              <input
                id="active"
                name="active"
                type="checkbox"
                className="form-check-input"
                checked={formState.active}
                onChange={(event) => setFormState((prev) => ({ ...prev, active: event.target.checked }))}
                disabled={isLoading || isSaving}
              />
              <label className="form-check-label" htmlFor="active">
                Ativar sincronizações automáticas
              </label>
            </div>
          </div>
        </div>

        <div className="d-flex flex-wrap gap-2 mt-4">
          <button type="submit" className="btn btn-primary" disabled={isSaving || isLoading}>
            {isSaving ? 'Salvando…' : 'Salvar configuração'}
          </button>
          <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={() => void handleTest()}
            disabled={isTesting || isLoading}
          >
            {isTesting ? 'Testando…' : 'Testar conexão'}
          </button>
        </div>

        {testMessage ? (
          <p className="text-success mt-3 mb-0">{testMessage}</p>
        ) : null}
      </form>

      <section className="card p-4">
        <h2 className="h5 mb-3">Sincronizações</h2>
        <p className="text-muted">Inicie as importações dos catálogos de filmes e séries. Você receberá notificações ao concluir.</p>

        <div className="row g-3">
          <div className="col-md-6">
            <SyncCard
              type="filmes"
              job={jobs.filmes}
              loading={syncing === 'filmes'}
              onRun={() => void handleSync('filmes')}
            />
          </div>
          <div className="col-md-6">
            <SyncCard
              type="series"
              job={jobs.series}
              loading={syncing === 'series'}
              onRun={() => void handleSync('series')}
            />
          </div>
        </div>
      </section>
    </section>
  );
}

interface SyncCardProps {
  type: ImportType;
  job: ImportJobHistoryItem | null;
  loading: boolean;
  onRun: () => void;
}

function SyncCard({ type, job, loading, onRun }: SyncCardProps) {
  const label = type === 'filmes' ? 'Filmes' : 'Séries';
  const statusLabel = job?.status ? job.status.toUpperCase() : 'Sem execuções';
  const summary = job
    ? `${job.startedAt ? new Date(job.startedAt).toLocaleString('pt-BR') : '—'} · ${job.inserted ?? 0} inseridos · ${job.updated ?? 0} atualizados`
    : 'Inicie uma sincronização para visualizar o histórico.';

  return (
    <div className="sync-card">
      <header className="sync-card__header">
        <div>
          <h3 className="sync-card__title">{label}</h3>
          <p className="sync-card__status">{statusLabel}</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={onRun} disabled={loading}>
          {loading ? 'Sincronizando…' : 'Sincronizar agora'}
        </button>
      </header>
      <p className="sync-card__summary">{summary}</p>
    </div>
  );
}
