import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import {
  fetchConfig,
  parseM3U,
  saveAccountConfig,
  saveUserSettings,
  testDatabaseConnection,
  type SaveUserSettingsPayload,
} from '../data/services/accountService';
import { getImports, runImport } from '../data/services/importService';
import type {
  AccountConfigPayload,
  ImportJobHistoryItem,
  ImportType,
  ParsedM3UResponse,
  UserConfigData,
} from '../data/types';
import { useToast } from '../providers/ToastProvider';
import {
  DB_ACCESS_DENIED_CODE,
  extractDbAccessDeniedMessage,
  extractDbAccessDeniedMessageFromApiError,
  extractDbAccessDeniedHint,
  extractDbAccessDeniedHintFromApiError,
  extractDbSslMisconfigMessage,
  extractDbSslMisconfigMessageFromApiError,
  getDbAccessDeniedFallbackMessage,
  isAccessDenied,
} from '../utils/dbErrors';
import { DbAccessDeniedNotice } from '../components/database/DbAccessDeniedNotice';

interface StatusMessage {
  type: 'success' | 'danger' | 'info';
  message: ReactNode;
}

type JobSummary = Record<ImportType, ImportJobHistoryItem | null>;

interface FormState {
  domain: string;
  port: string;
  username: string;
  password: string;
  active: boolean;
  dbHost: string;
  dbPort: string;
  dbUser: string;
  dbPassword: string;
  dbName: string;
}

interface AccessDeniedContentOptions {
  error?: { code?: string | null; message?: string | null } | null;
  fallbackMessage?: string | null | undefined;
  hint?: string | null | undefined;
}

interface MysqlUriParts {
  host: string;
  port: number | null;
  username: string;
  password: string;
  database: string;
}

function decodeMysqlComponent(value: string): string {
  try {
    return decodeURIComponent(value.replace(/\+/g, '%20'));
  } catch (error) {
    console.warn('Não foi possível decodificar componente da URI do banco.', error);
    return value;
  }
}

function parseMysqlUri(uri: string | null | undefined): MysqlUriParts | null {
  if (!uri || typeof uri !== 'string') {
    return null;
  }

  try {
    const normalized = uri.includes('://') ? uri : `mysql+pymysql://${uri}`;
    const parsed = new URL(normalized);
    const database = parsed.pathname.replace(/^\//, '');

    return {
      host: parsed.hostname ?? '',
      port: parsed.port ? Number(parsed.port) : null,
      username: decodeMysqlComponent(parsed.username),
      password: decodeMysqlComponent(parsed.password ?? ''),
      database: decodeMysqlComponent(database),
    };
  } catch (error) {
    console.warn('Falha ao interpretar URI do banco XUI.', error);
    return null;
  }
}

function buildMysqlUri(options: {
  host: string;
  port?: number | null | undefined;
  username: string;
  password?: string | null | undefined;
  database: string;
}): string | null {
  const host = options.host.trim();
  const username = options.username.trim();
  const database = options.database.trim();

  if (!host || !username || !database) {
    return null;
  }

  let port = 3306;
  if (typeof options.port === 'number' && Number.isFinite(options.port) && options.port > 0) {
    port = options.port;
  }

  const encodedUser = encodeURIComponent(username);
  const encodedPassword =
    options.password && options.password.length > 0 ? `:${encodeURIComponent(options.password)}` : '';
  const encodedDatabase = encodeURIComponent(database);

  return `mysql+pymysql://${encodedUser}${encodedPassword}@${host}:${port}/${encodedDatabase}`;
}

function createAccessDeniedContent({
  error,
  fallbackMessage,
  hint,
}: AccessDeniedContentOptions): ReactNode {
  const messageSource = [fallbackMessage, error?.message].find(
    (value): value is string => typeof value === 'string' && value.trim().length > 0,
  );

  const normalizedError = {
    code: error?.code ?? DB_ACCESS_DENIED_CODE,
    message: messageSource ? messageSource.trim() : getDbAccessDeniedFallbackMessage(),
  };

  const normalizedHint =
    typeof hint === 'string' && hint.trim().length > 0 ? hint.trim() : null;

  return <DbAccessDeniedNotice error={normalizedError} hint={normalizedHint} />;
}

export default function AccountConfig() {
  const { push } = useToast();
  const [link, setLink] = useState('');
  const [config, setConfig] = useState<UserConfigData | null>(null);
  const [formState, setFormState] = useState<FormState>({
    domain: '',
    port: '',
    username: '',
    password: '',
    active: false,
    dbHost: '',
    dbPort: '',
    dbUser: '',
    dbPassword: '',
    dbName: '',
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isParsing, setIsParsing] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isTestingDb, setIsTestingDb] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<StatusMessage | null>(null);
  const [dbStatus, setDbStatus] = useState<StatusMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobSummary>({ filmes: null, series: null });
  const [syncing, setSyncing] = useState<ImportType | null>(null);

  const hasExistingPanelPassword = Boolean(config?.hasPassword || config?.password);
  const hasExistingDbPassword = Boolean(config?.dbPasswordMasked);

  const applySettings = useCallback(
    (
      data: UserConfigData | null,
      options: { showEmptyMessage?: boolean; preserveStatus?: boolean } = {},
    ) => {
      const { showEmptyMessage = false, preserveStatus = false } = options;

      const resetForm = () => {
        setFormState({
          domain: '',
          port: '',
          username: '',
          password: '',
          active: false,
          dbHost: '',
          dbPort: '',
          dbUser: '',
          dbPassword: '',
          dbName: '',
        });
        setLink('');
      };

    if (!data) {
      setConfig(null);
      resetForm();
      setDbStatus(null);
      if (!preserveStatus) {
        setStatus(showEmptyMessage ? { type: 'info', message: 'Nenhuma configuração encontrada' } : null);
      }
      return false;
    }

      const normalizedDomain = data.domain ?? '';
      const normalizedPort =
        typeof data.port === 'number' && Number.isFinite(data.port) ? String(data.port) : '';
      const normalizedUsername = data.username ?? '';
      const normalizedPassword = data.password ?? '';
      const normalizedActive = typeof data.active === 'boolean' ? data.active : Boolean(data.active);
      const normalizedDbHost = data.dbHost ?? '';
      const normalizedDbPort =
        typeof data.dbPort === 'number' && Number.isFinite(data.dbPort) ? String(data.dbPort) : '';
      const normalizedDbUser = data.dbUser ?? '';
      const normalizedDbName = data.dbName ?? '';
      const normalizedLink =
        typeof data.linkM3u === 'string'
          ? data.linkM3u
          : typeof data.link === 'string'
          ? data.link
          : '';

      setConfig(data);
      setLink(normalizedLink);
      setFormState({
        domain: normalizedDomain,
        port: normalizedPort,
        username: normalizedUsername,
        password: normalizedPassword,
        active: normalizedActive,
        dbHost: normalizedDbHost,
        dbPort: normalizedDbPort,
        dbUser: normalizedDbUser,
        dbPassword: '',
        dbName: normalizedDbName,
      });

      if (data.dbConnectionStatus) {
        const type = data.dbConnectionStatus === 'success' ? 'success' : 'danger';
        let message =
          data.dbConnectionMessage ??
          (data.dbConnectionStatus === 'success'
            ? 'Conexão com o banco XUI validada.'
            : 'Falha ao validar a conexão com o banco XUI.');
        if (data.dbTestedAt) {
          try {
            const testedDate = new Date(data.dbTestedAt);
            if (!Number.isNaN(testedDate.getTime())) {
              message = `${message} (${testedDate.toLocaleString('pt-BR')})`;
            }
          } catch (err) {
            console.warn('Não foi possível formatar data do teste do banco.', err);
          }
        }
        setDbStatus({ type, message });
      } else {
        setDbStatus(null);
      }

      const hasData =
        Boolean(normalizedDomain.trim()) ||
        Boolean(normalizedPort.trim()) ||
        Boolean(normalizedUsername.trim()) ||
        Boolean(normalizedPassword.trim()) ||
        Boolean(normalizedLink.trim()) ||
        Boolean(normalizedDbHost.trim()) ||
        Boolean(normalizedDbUser.trim()) ||
        Boolean(normalizedDbName.trim());

      if (!preserveStatus) {
        if (!hasData) {
          setStatus(showEmptyMessage ? { type: 'info', message: 'Nenhuma configuração encontrada' } : null);
        } else if (data.connectionReady) {
          setStatus({ type: 'success', message: 'Conexão com o XUI configurada.' });
        } else {
          setStatus(null);
        }
      }

      return hasData;
    },
    [],
  );

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

        applySettings(response, { showEmptyMessage: true });

        await loadImports();
      } catch (err) {
        if (!cancelled) {
          const apiError = err as ApiError;
          if (apiError?.status === 404) {
            applySettings(null, { showEmptyMessage: true });
          } else {
            setError(apiError?.message ?? 'Não foi possível carregar a configuração.');
          }
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
  }, [applySettings, loadImports]);

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
    if (isTesting || isSaving) {
      return;
    }

    setIsTesting(true);
    setError(null);
    setStatus(null);

    const trimmedDomain = formState.domain.trim();
    const trimmedUsername = formState.username.trim();
    const trimmedPort = formState.port.trim();
    const trimmedDbHost = formState.dbHost.trim();
    const trimmedDbPort = formState.dbPort.trim();
    const trimmedDbUser = formState.dbUser.trim();
    const trimmedDbPassword = formState.dbPassword.trim();
    const trimmedDbName = formState.dbName.trim();

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

    let numericDbPort: number | null = null;
    if (trimmedDbPort) {
      const parsedPort = Number(trimmedDbPort);
      if (Number.isNaN(parsedPort)) {
        setError('Porta do banco inválida.');
        setIsTesting(false);
        return;
      }
      numericDbPort = parsedPort;
    }

    const existingUri = parseMysqlUri(config?.xuiDbUri ?? null);
    const effectiveHost = trimmedDbHost || existingUri?.host || '';
    const effectiveUser = trimmedDbUser || existingUri?.username || '';
    const effectiveDatabase = trimmedDbName || existingUri?.database || '';
    const effectivePort =
      numericDbPort ??
      (existingUri?.port !== null && existingUri?.port !== undefined ? existingUri.port : undefined) ??
      (typeof config?.dbPort === 'number' ? config.dbPort : undefined);

    let effectivePassword: string | null | undefined;
    if (trimmedDbPassword) {
      effectivePassword = trimmedDbPassword;
    } else if (existingUri) {
      effectivePassword = existingUri.password;
    } else {
      effectivePassword = '';
    }

    const resolvedDbUri = buildMysqlUri({
      host: effectiveHost,
      port: effectivePort,
      username: effectiveUser,
      password: effectivePassword,
      database: effectiveDatabase,
    });

    if (resolvedDbUri) {
      payload.xuiDbUri = resolvedDbUri;
    } else if (config?.xuiDbUri) {
      payload.xuiDbUri = config.xuiDbUri;
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
      if (isAccessDenied(apiError)) {
        const message = extractDbAccessDeniedMessageFromApiError(apiError);
        const hint = extractDbAccessDeniedHintFromApiError(apiError);
        const notice = createAccessDeniedContent({
          error: { code: apiError?.code, message: apiError?.message },
          fallbackMessage: message,
          hint,
        });
        setStatus({ type: 'danger', message: notice });
        setError(null);
        push(notice, 'error', { duration: 15000 });
      } else {
        setError(apiError?.message ?? 'Não foi possível validar a conexão.');
      }
    } finally {
      setIsTesting(false);
    }
  }

  async function handleTestDb() {
    if (isTestingDb || isSaving) {
      return;
    }

    const trimmedDbHost = formState.dbHost.trim();
    const trimmedDbPort = formState.dbPort.trim();
    const trimmedDbUser = formState.dbUser.trim();
    const trimmedDbPassword = formState.dbPassword.trim();
    const trimmedDbName = formState.dbName.trim();

    if (!trimmedDbHost || !trimmedDbName) {
      setDbStatus({ type: 'danger', message: 'Informe host e nome do banco XUI.' });
      return;
    }

    if (trimmedDbPort) {
      const numericDbPort = Number(trimmedDbPort);
      if (Number.isNaN(numericDbPort)) {
        setDbStatus({ type: 'danger', message: 'Porta do banco inválida.' });
        return;
      }
    }

    setIsTestingDb(true);
    setDbStatus(null);
    setError(null);

    const payload: Partial<SaveUserSettingsPayload> = {
      db_host: trimmedDbHost,
      db_name: trimmedDbName,
    };

    if (trimmedDbPort) {
      payload.db_port = Number(trimmedDbPort);
    }
    if (trimmedDbUser) {
      payload.db_user = trimmedDbUser;
    }
    if (trimmedDbPassword) {
      payload.db_password = trimmedDbPassword;
    }

    try {
      const response = await testDatabaseConnection(payload);

      if (response.error?.code === DB_ACCESS_DENIED_CODE || isAccessDenied(response)) {
        const notice = createAccessDeniedContent({
          error: response.error,
          fallbackMessage:
            extractDbAccessDeniedMessage(response) ??
            response.error?.message ??
            response.message,
          hint: response.hint ?? extractDbAccessDeniedHint(response),
        });
        setDbStatus({ type: 'danger', message: notice });
        push(notice, 'error', { duration: 15000 });
        return;
      }

      const sslMessage = extractDbSslMisconfigMessage(response);

      if (response.success === false) {
        if (sslMessage) {
          setDbStatus({ type: 'danger', message: sslMessage });
          push(`⚠️ ${sslMessage}`, 'error');
          return;
        }

        const fallbackMessage =
          response.error?.message ||
          response.message ||
          'Não foi possível validar a conexão com o banco.';
        setDbStatus({ type: 'danger', message: fallbackMessage });
        push(fallbackMessage, 'error');
        return;
      }

      let message = response.message || 'Conexão estabelecida com sucesso.';
      if (response.testedAt) {
        try {
          const testedDate = new Date(response.testedAt);
          if (!Number.isNaN(testedDate.getTime())) {
            message = `${message} (${testedDate.toLocaleString('pt-BR')})`;
          }
        } catch (err) {
          console.warn('Não foi possível formatar data do teste do banco.', err);
        }
      }
      setDbStatus({ type: 'success', message });
      push('Conexão com o banco verificada.', 'success');
    } catch (err) {
      const apiError = err as ApiError;
      const sslMessage = extractDbSslMisconfigMessageFromApiError(apiError);

      if (isAccessDenied(apiError)) {
        const message = extractDbAccessDeniedMessageFromApiError(apiError);
        const hint = extractDbAccessDeniedHintFromApiError(apiError);
        const notice = createAccessDeniedContent({
          error: { code: apiError?.code, message: apiError?.message },
          fallbackMessage: message,
          hint,
        });
        setDbStatus({ type: 'danger', message: notice });
        push(notice, 'error', { duration: 15000 });
      } else if (sslMessage) {
        setDbStatus({ type: 'danger', message: sslMessage });
        push(`⚠️ ${sslMessage}`, 'error');
      } else {
        setDbStatus({
          type: 'danger',
          message: apiError?.message ?? 'Não foi possível validar a conexão com o banco.',
        });
      }
    } finally {
      setIsTestingDb(false);
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

  async function handleSave() {
    if (isSaving) {
      return;
    }

    const trimmedDomain = formState.domain.trim();
    const trimmedUsername = formState.username.trim();
    const trimmedPort = formState.port.trim();
    const trimmedPassword = formState.password.trim();
    const trimmedLink = link.trim();
    const trimmedDbHost = formState.dbHost.trim();
    const trimmedDbPort = formState.dbPort.trim();
    const trimmedDbUser = formState.dbUser.trim();
    const trimmedDbPassword = formState.dbPassword.trim();
    const trimmedDbName = formState.dbName.trim();

    if (trimmedPort) {
      const numericPort = Number(trimmedPort);
      if (Number.isNaN(numericPort)) {
        setError('Porta inválida.');
        return;
      }
    }

    if (trimmedDbPort) {
      const numericDbPort = Number(trimmedDbPort);
      if (Number.isNaN(numericDbPort)) {
        setError('Porta do banco inválida.');
        return;
      }
    }

    if (!trimmedDbHost || !trimmedDbName) {
      setError('Informe host e nome do banco XUI.');
      return;
    }

    setIsSaving(true);
    setError(null);

    const payload: SaveUserSettingsPayload = {
      link_m3u: trimmedLink || null,
      domain: trimmedDomain || null,
      username: trimmedUsername || null,
      active: formState.active,
      db_host: trimmedDbHost,
      db_name: trimmedDbName,
    };

    if (trimmedPort) {
      payload.port = Number(trimmedPort);
    } else {
      payload.port = null;
    }

    payload.db_port = trimmedDbPort ? Number(trimmedDbPort) : 3306;

    payload.db_user = trimmedDbUser || null;

    if (trimmedPassword) {
      payload.password = trimmedPassword;
    } else {
      payload.password = null;
    }

    if (trimmedDbPassword) {
      payload.db_password = trimmedDbPassword;
    }

    try {
      const saved = await saveUserSettings(payload);
      const hasData = applySettings(saved, { showEmptyMessage: true, preserveStatus: true });
      if (hasData) {
        setStatus({ type: 'success', message: 'Configurações salvas com sucesso' });
      } else {
        setStatus({ type: 'info', message: 'Nenhuma configuração encontrada' });
      }
      push('Configurações salvas com sucesso', 'success');
      setFormState((prev) => ({ ...prev, password: '', dbPassword: '' }));
    } catch (err) {
      const apiError = err as ApiError;
      if (isAccessDenied(apiError)) {
        const message = extractDbAccessDeniedMessageFromApiError(apiError);
        const hint = extractDbAccessDeniedHintFromApiError(apiError);
        const notice = createAccessDeniedContent({
          error: { code: apiError?.code, message: apiError?.message },
          fallbackMessage: message,
          hint,
        });
        setStatus({ type: 'danger', message: notice });
        setError(null);
        push(notice, 'error', { duration: 15000 });
      } else {
        setError(apiError?.message ?? 'Não foi possível salvar as configurações.');
      }
    } finally {
      setIsSaving(false);
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
        <div
          className={`alert alert-${status.type} mb-4`}
          role="status"
          style={{ whiteSpace: 'pre-line' }}
        >
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
            disabled={isLoading || isParsing || isTesting || isSaving || isTestingDb}
          />
        </div>
        <div className="col-12 col-lg-3 d-flex align-items-end">
          <button
            type="button"
            className="btn btn-outline-primary w-100"
            onClick={handleParse}
            disabled={isParsing || isLoading || !link.trim() || isSaving || isTestingDb}
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
              disabled={isLoading || isTesting || isSaving || isTestingDb}
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
              disabled={isLoading || isTesting || isSaving || isTestingDb}
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
              disabled={isLoading || isTesting || isSaving || isTestingDb}
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
              placeholder={hasExistingPanelPassword ? 'Manter senha atual' : 'Senha do painel'}
              value={formState.password}
              onChange={(event) => setFormState((prev) => ({ ...prev, password: event.target.value }))}
              disabled={isLoading || isTesting || isSaving || isTestingDb}
              minLength={4}
              required={!hasExistingPanelPassword}
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
                disabled={isLoading || isTesting || isSaving || isTestingDb}
              />
              <label className="form-check-label" htmlFor="active">
                Ativar sincronizações automáticas
              </label>
            </div>
          </div>

          <div className="col-12 mt-4">
            <h2 className="h5 mb-3">Banco de Dados XUI</h2>
            {dbStatus ? (
              <div
                className={`alert alert-${dbStatus.type} mb-3`}
                role="status"
                style={{ whiteSpace: 'pre-line' }}
              >
                {dbStatus.message}
              </div>
            ) : null}
          </div>

          <div className="col-md-4">
            <label className="form-label" htmlFor="dbHost">
              Host
            </label>
            <input
              id="dbHost"
              name="dbHost"
              type="text"
              className="form-control"
              placeholder="ex: 127.0.0.1"
              value={formState.dbHost}
              onChange={(event) => setFormState((prev) => ({ ...prev, dbHost: event.target.value }))}
              disabled={isLoading || isTesting || isSaving || isTestingDb}
              required
            />
          </div>

          <div className="col-md-2">
            <label className="form-label" htmlFor="dbPort">
              Porta
            </label>
            <input
              id="dbPort"
              name="dbPort"
              type="number"
              min={0}
              max={65535}
              className="form-control"
              placeholder="3306"
              value={formState.dbPort}
              onChange={(event) => setFormState((prev) => ({ ...prev, dbPort: event.target.value }))}
              disabled={isLoading || isTesting || isSaving || isTestingDb}
            />
          </div>

          <div className="col-md-3">
            <label className="form-label" htmlFor="dbUser">
              Usuário
            </label>
            <input
              id="dbUser"
              name="dbUser"
              type="text"
              className="form-control"
              placeholder="root"
              value={formState.dbUser}
              onChange={(event) => setFormState((prev) => ({ ...prev, dbUser: event.target.value }))}
              disabled={isLoading || isTesting || isSaving || isTestingDb}
            />
          </div>

          <div className="col-md-3">
            <label className="form-label" htmlFor="dbPassword">
              Senha
            </label>
            <input
              id="dbPassword"
              name="dbPassword"
              type="password"
              className="form-control"
              placeholder={hasExistingDbPassword ? 'Manter senha atual' : 'Senha do banco'}
              value={formState.dbPassword}
              onChange={(event) => setFormState((prev) => ({ ...prev, dbPassword: event.target.value }))}
              disabled={isLoading || isTesting || isSaving || isTestingDb}
            />
          </div>

          <div className="col-md-4">
            <label className="form-label" htmlFor="dbName">
              Nome do banco
            </label>
            <input
              id="dbName"
              name="dbName"
              type="text"
              className="form-control"
              placeholder="xui"
              value={formState.dbName}
              onChange={(event) => setFormState((prev) => ({ ...prev, dbName: event.target.value }))}
              disabled={isLoading || isTesting || isSaving || isTestingDb}
              required
            />
          </div>

          <div className="col-12 d-flex justify-content-end">
            <button
              type="button"
              className="btn btn-outline-secondary"
              onClick={() => void handleTestDb()}
              disabled={isTestingDb || isSaving || isLoading || isTesting}
            >
              {isTestingDb ? 'Testando banco…' : 'Testar conexão com banco'}
            </button>
          </div>
        </div>

        <div className="d-flex flex-wrap gap-2 mt-4">
          <button
            type="button"
            className="btn btn-success"
            onClick={() => void handleSave()}
            disabled={isSaving || isLoading || isTesting || isTestingDb}
          >
            {isSaving ? 'Salvando…' : 'Salvar configurações'}
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isTesting || isLoading || isSaving || isTestingDb}
          >
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
