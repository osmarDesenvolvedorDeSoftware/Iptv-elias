import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { fetchConfig, parseM3U, saveAccountConfig } from '../data/services/accountService';
import { getImports, runImport } from '../data/services/importService';
import type {
  AccountConfigPayload,
  ImportJobHistoryItem,
  ImportType,
  ParsedM3UResponse,
  UserConfigData,
} from '../data/types';
import { useToast } from '../providers/ToastProvider';

interface StatusMessage {
  type: 'success' | 'danger' | 'info';
  message: string;
}

type JobSummary = Record<ImportType, ImportJobHistoryItem | null>;

export default function AccountConfig() {
  const { push } = useToast();
  const [link, setLink] = useState('');
  const [config, setConfig] = useState<UserConfigData | null>(null);
  const [formState, setFormState] = useState({
    domain: '',
    port: '',
    username: '',
    password: '',
    active: true,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isParsing, setIsParsing] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [status, setStatus] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobSummary>({ filmes: null, series: null });
  const [syncing, setSyncing] = useState<ImportType | null>(null);

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

        if (response.connectionReady) {
          setStatus({ type: 'success', message: 'Conexão com o XUI configurada.' });
        }

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

  async function handleParse(event: FormEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (!link.trim() || isParsing) {
      return;
    }

    setIsParsing(true);
    setStatus(null);
    setError(null);

    try {
      const parsed: ParsedM3UResponse = await parseM3U(link.trim());
      setFormState((prev) => ({
        ...prev,
        domain: parsed.domain ?? '',
        port: parsed.port ? String(parsed.port) : '',
        username: parsed.username ?? '',
        password: parsed.password ?? '',
      }));
      setStatus({ type: 'info', message: 'Dados extraídos do link M3U.' });
      push('Link M3U analisado com sucesso.', 'success');
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível extrair os dados do link M3U.');
    } finally {
      setIsParsing(false);
    }
  }

  async function handleTestConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isTesting) {
      return;
    }

    setIsTesting(true);
    setError(null);
    setStatus(null);

    const trimmedDomain = formState.domain.trim();
    const trimmedUsername = formState.username.trim();
    const trimmedPort = formState.port.trim();

    const payload: AccountConfigPayload = {
      domain: trimmedDomain || null,
      username: trimmedUsername || null,
      active: formState.active,
    };

    if (trimmedPort) {
      const numericPort = Number(trimmedPort);
      if (Number.isNaN(numericPort)) {
        setError('Porta inválida.');
        setIsTesting(false);
        return;
      }
      payload.port = numericPort;
    }

    const trimmedPassword = formState.password.trim();
    if (trimmedPassword) {
      payload.password = trimmedPassword;
    }

    if (link.trim()) {
      payload.link_m3u = link.trim();
    }

    try {
      const response = await saveAccountConfig(payload);
      setConfig(response);
      setFormState((prev) => ({ ...prev, password: '' }));
      const successMessage = response.connectionReady
        ? 'Conexão validada e salva com sucesso.'
        : 'Configuração salva, mas a conexão não pôde ser validada.';
      setStatus({ type: response.connectionReady ? 'success' : 'danger', message: successMessage });
      push('Configuração atualizada.', 'success');
      await loadImports();
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível validar a conexão.');
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
      push(`Sincronização de ${type} iniciada.`, 'info');
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
          <h1 className="dashboard__title">Configurar Painel XUI</h1>
          <p className="dashboard__subtitle">
            Cole o link M3U fornecido pela operadora e valide a conexão com o banco XUI.
          </p>
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

      {status ? (
        <div className={`alert alert-${status.type} mb-4`} role="status">
          {status.message}
        </div>
      ) : null}

      <form className="card p-4 mb-4" onSubmit={handleTestConnection}>
        <div className="row g-3">
          <div className="col-12 col-lg-9">
            <label className="form-label" htmlFor="link">
              Link M3U
            </label>
            <input
              id="link"
              name="link"
              type="text"
              className="form-control"
              placeholder="https://painel.tv/get.php?username=USUARIO&password=SENHA&type=m3u"
              value={link}
              onChange={(event) => setLink(event.target.value)}
              disabled={isLoading || isParsing || isTesting}
            />
          </div>
          <div className="col-12 col-lg-3 d-flex align-items-end">
            <button
              type="button"
              className="btn btn-outline-primary w-100"
              onClick={handleParse}
              disabled={isParsing || isLoading || !link.trim()}
            >
              {isParsing ? 'Extraindo…' : 'Extrair dados'}
            </button>
          </div>

          <div className="col-md-6">
            <label className="form-label" htmlFor="domain">
              Domínio ou IP
            </label>
            <input
              id="domain"
              name="domain"
              type="text"
              className="form-control"
              placeholder="ex: painel.exemplo.com"
              value={formState.domain}
              onChange={(event) => setFormState((prev) => ({ ...prev, domain: event.target.value }))}
              disabled={isLoading || isTesting}
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
              disabled={isLoading || isTesting}
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
              disabled={isLoading || isTesting}
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
              placeholder={hasExistingPassword ? 'Manter senha atual' : 'Senha do painel'}
              value={formState.password}
              onChange={(event) => setFormState((prev) => ({ ...prev, password: event.target.value }))}
              disabled={isLoading || isTesting}
              minLength={4}
              required={!hasExistingPassword}
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
                disabled={isLoading || isTesting}
              />
              <label className="form-check-label" htmlFor="active">
                Ativar sincronizações automáticas
              </label>
            </div>
          </div>
        </div>

        <div className="d-flex flex-wrap gap-2 mt-4">
          <button type="submit" className="btn btn-primary" disabled={isTesting || isLoading}>
            {isTesting ? 'Validando…' : 'Testar conexão'}
          </button>
        </div>
      </form>

      <section className="card p-4">
        <h2 className="h5 mb-3">Sincronizações</h2>
        <p className="text-muted">
          Inicie as importações dos catálogos de filmes e séries. Você receberá notificações ao concluir.
        </p>

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
