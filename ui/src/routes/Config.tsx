import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';

import { getConfig, saveConfig } from '../data/services/configService';
import { ConfigResponse } from '../data/types';
import { useToast } from '../providers/ToastProvider';

type TabKey = 'importer' | 'tmdb' | 'notifications';

type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement>;

const tabLabels: Record<TabKey, string> = {
  importer: 'Importador',
  tmdb: 'TMDb',
  notifications: 'Notificações',
};

function cloneConfig(config: ConfigResponse): ConfigResponse {
  return JSON.parse(JSON.stringify(config));
}

function isConfigValid(config: ConfigResponse): boolean {
  if (!config.tmdb.apiKey.trim()) {
    return false;
  }

  if (!config.tmdb.language.trim()) {
    return false;
  }

  if (!config.tmdb.region.trim()) {
    return false;
  }

  if (!Number.isFinite(config.importer.movieDelayMs) || config.importer.movieDelayMs < 0) {
    return false;
  }

  if (!Number.isFinite(config.importer.seriesDelayMs) || config.importer.seriesDelayMs < 0) {
    return false;
  }

  if (!Number.isFinite(config.importer.maxParallelJobs) || config.importer.maxParallelJobs < 1) {
    return false;
  }

  return true;
}

export default function Configuracoes() {
  const { push } = useToast();
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [initialConfig, setInitialConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('importer');
  const [saving, setSaving] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [restartRequired, setRestartRequired] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const hasChanges = useMemo(() => {
    if (!config || !initialConfig) {
      return false;
    }

    return JSON.stringify(config) !== JSON.stringify(initialConfig);
  }, [config, initialConfig]);

  const defaultCategoriesText = useMemo(() => {
    if (!config) {
      return '';
    }

    return config.importer.defaultCategories.join(', ');
  }, [config]);

  const tmdbErrors = {
    apiKey: showErrors && !config?.tmdb.apiKey.trim(),
    language: showErrors && !config?.tmdb.language.trim(),
    region: showErrors && !config?.tmdb.region.trim(),
  };

  const importerErrors = {
    movieDelay: showErrors && !!config && config.importer.movieDelayMs < 0,
    seriesDelay: showErrors && !!config && config.importer.seriesDelayMs < 0,
    maxParallel: showErrors && !!config && config.importer.maxParallelJobs < 1,
  };

  async function loadConfig() {
    setLoading(true);
    setError(null);

    try {
      const response = await getConfig();
      setConfig(cloneConfig(response));
      setInitialConfig(cloneConfig(response));
      setRestartRequired(false);
      setShowErrors(false);
    } catch (loadError) {
      console.error(loadError);
      setError('Não foi possível carregar as configurações mockadas.');
    } finally {
      setLoading(false);
    }
  }

  function handleInputChange(event: InputEvent) {
    if (!config) {
      return;
    }

    const { name, value, type, checked } = event.target;

    setConfig((current) => {
      if (!current) {
        return current;
      }

      switch (name) {
        case 'tmdb.apiKey':
          return { ...current, tmdb: { ...current.tmdb, apiKey: value } };
        case 'tmdb.language':
          return { ...current, tmdb: { ...current.tmdb, language: value } };
        case 'tmdb.region':
          return { ...current, tmdb: { ...current.tmdb, region: value.toUpperCase() } };
        case 'importer.movieDelayMs':
          return {
            ...current,
            importer: { ...current.importer, movieDelayMs: Number(value) },
          };
        case 'importer.seriesDelayMs':
          return {
            ...current,
            importer: { ...current.importer, seriesDelayMs: Number(value) },
          };
        case 'importer.maxParallelJobs':
          return {
            ...current,
            importer: { ...current.importer, maxParallelJobs: Number(value) },
          };
        case 'importer.useImageCache':
          return {
            ...current,
            importer: { ...current.importer, useImageCache: type === 'checkbox' ? checked : Boolean(value) },
          };
        case 'notifications.emailAlerts':
          return {
            ...current,
            notifications: { ...current.notifications, emailAlerts: type === 'checkbox' ? checked : Boolean(value) },
          };
        case 'notifications.webhookUrl': {
          const sanitized = value.trim();
          return {
            ...current,
            notifications: {
              ...current.notifications,
              webhookUrl: sanitized.length === 0 ? null : sanitized,
            },
          };
        }
        default:
          return current;
      }
    });
  }

  function handleDefaultCategoriesChange(event: ChangeEvent<HTMLInputElement>) {
    const categories = event.target.value
      .split(',')
      .map((category) => category.trim())
      .filter(Boolean);

    setConfig((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        importer: {
          ...current.importer,
          defaultCategories: categories,
        },
      };
    });
  }

  function handleTabChange(tab: TabKey) {
    setActiveTab(tab);
  }

  function handleReset() {
    if (!initialConfig) {
      return;
    }

    setConfig(cloneConfig(initialConfig));
    setShowErrors(false);
    setRestartRequired(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!config) {
      return;
    }

    setShowErrors(true);

    if (!isConfigValid(config)) {
      push('Revise os campos obrigatórios antes de salvar.', 'error');
      return;
    }

    setSaving(true);

    try {
      const response = await saveConfig(config);
      setInitialConfig(cloneConfig(config));
      setRestartRequired(response.requiresWorkerRestart);
      push('Configurações salvas com sucesso', 'success');
    } catch (saveError) {
      console.error(saveError);
      push('Erro ao salvar as configurações.', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="container-fluid py-4">
      <header className="d-flex flex-column align-items-center mb-4 text-center">
        <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
          Dashboard / Configurações
        </nav>
        <h1 className="display-6 mb-0">Configurações</h1>
      </header>

      {error ? (
        <div className="alert alert-danger d-flex flex-column flex-md-row align-items-md-center justify-content-between" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-outline-light mt-3 mt-md-0" onClick={loadConfig}>
            Tentar novamente
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="card shadow-sm" aria-busy="true">
          <div className="card-body">
            <div className="placeholder-glow">
              <div className="placeholder col-12 mb-3" style={{ height: '1.75rem' }} />
              <div className="placeholder col-10 mb-3" style={{ height: '1.75rem' }} />
              <div className="placeholder col-8" style={{ height: '1.75rem' }} />
            </div>
          </div>
        </div>
      ) : config ? (
        <form onSubmit={handleSubmit}>
          <div className="card shadow-sm">
            <div className="card-header pb-0">
              <ul className="nav nav-tabs card-header-tabs">
                {(Object.keys(tabLabels) as TabKey[]).map((tab) => (
                  <li className="nav-item" key={tab}>
                    <button
                      type="button"
                      className={`nav-link${activeTab === tab ? ' active' : ''}`}
                      onClick={() => handleTabChange(tab)}
                    >
                      {tabLabels[tab]}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="card-body">
              {restartRequired ? (
                <div className="alert alert-warning" role="alert">
                  Alterações aplicadas exigem reinício do worker de importação.
                </div>
              ) : null}

              {activeTab === 'importer' ? (
                <div className="row g-4">
                  <div className="col-12 col-md-4">
                    <label htmlFor="importer-movie-delay" className="form-label text-uppercase small text-muted">
                      Delay entre filmes (ms)
                    </label>
                    <input
                      id="importer-movie-delay"
                      type="number"
                      min={0}
                      className={`form-control${importerErrors.movieDelay ? ' is-invalid' : ''}`}
                      name="importer.movieDelayMs"
                      value={config.importer.movieDelayMs}
                      onChange={handleInputChange}
                    />
                    {importerErrors.movieDelay ? (
                      <div className="invalid-feedback">Informe um valor maior ou igual a 0.</div>
                    ) : null}
                  </div>
                  <div className="col-12 col-md-4">
                    <label htmlFor="importer-series-delay" className="form-label text-uppercase small text-muted">
                      Delay entre séries (ms)
                    </label>
                    <input
                      id="importer-series-delay"
                      type="number"
                      min={0}
                      className={`form-control${importerErrors.seriesDelay ? ' is-invalid' : ''}`}
                      name="importer.seriesDelayMs"
                      value={config.importer.seriesDelayMs}
                      onChange={handleInputChange}
                    />
                    {importerErrors.seriesDelay ? (
                      <div className="invalid-feedback">Informe um valor maior ou igual a 0.</div>
                    ) : null}
                  </div>
                  <div className="col-12 col-md-4">
                    <label htmlFor="importer-max-parallel" className="form-label text-uppercase small text-muted">
                      Jobs paralelos
                    </label>
                    <input
                      id="importer-max-parallel"
                      type="number"
                      min={1}
                      className={`form-control${importerErrors.maxParallel ? ' is-invalid' : ''}`}
                      name="importer.maxParallelJobs"
                      value={config.importer.maxParallelJobs}
                      onChange={handleInputChange}
                    />
                    {importerErrors.maxParallel ? (
                      <div className="invalid-feedback">Defina ao menos 1 job em paralelo.</div>
                    ) : null}
                  </div>
                  <div className="col-12">
                    <label htmlFor="importer-default-categories" className="form-label text-uppercase small text-muted">
                      Categorias padrão
                    </label>
                    <input
                      id="importer-default-categories"
                      type="text"
                      className="form-control"
                      placeholder="Separadas por vírgula"
                      value={defaultCategoriesText}
                      onChange={handleDefaultCategoriesChange}
                    />
                    <small className="text-muted">As categorias são aplicadas automaticamente em novas importações.</small>
                  </div>
                  <div className="col-12">
                    <div className="custom-control custom-switch">
                      <input
                        id="importer-use-cache"
                        type="checkbox"
                        className="custom-control-input"
                        name="importer.useImageCache"
                        checked={config.importer.useImageCache}
                        onChange={handleInputChange}
                      />
                      <label className="custom-control-label" htmlFor="importer-use-cache">
                        Usar cache de imagens da última execução
                      </label>
                    </div>
                  </div>
                </div>
              ) : null}

              {activeTab === 'tmdb' ? (
                <div className="row g-4">
                  <div className="col-12 col-md-6">
                    <label htmlFor="tmdb-api-key" className="form-label text-uppercase small text-muted">
                      API Key
                    </label>
                    <input
                      id="tmdb-api-key"
                      type="text"
                      className={`form-control${tmdbErrors.apiKey ? ' is-invalid' : ''}`}
                      name="tmdb.apiKey"
                      value={config.tmdb.apiKey}
                      onChange={handleInputChange}
                    />
                    {tmdbErrors.apiKey ? (
                      <div className="invalid-feedback">Informe a chave da API do TMDb.</div>
                    ) : null}
                  </div>
                  <div className="col-12 col-md-3">
                    <label htmlFor="tmdb-language" className="form-label text-uppercase small text-muted">
                      Idioma padrão
                    </label>
                    <input
                      id="tmdb-language"
                      type="text"
                      className={`form-control${tmdbErrors.language ? ' is-invalid' : ''}`}
                      name="tmdb.language"
                      value={config.tmdb.language}
                      onChange={handleInputChange}
                    />
                    {tmdbErrors.language ? (
                      <div className="invalid-feedback">Informe o idioma padrão (ex.: pt-BR).</div>
                    ) : null}
                  </div>
                  <div className="col-12 col-md-3">
                    <label htmlFor="tmdb-region" className="form-label text-uppercase small text-muted">
                      Região
                    </label>
                    <input
                      id="tmdb-region"
                      type="text"
                      maxLength={2}
                      className={`form-control${tmdbErrors.region ? ' is-invalid' : ''}`}
                      name="tmdb.region"
                      value={config.tmdb.region}
                      onChange={handleInputChange}
                    />
                    {tmdbErrors.region ? (
                      <div className="invalid-feedback">Informe a região (ex.: BR).</div>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {activeTab === 'notifications' ? (
                <div className="row g-4">
                  <div className="col-12">
                    <div className="custom-control custom-checkbox">
                      <input
                        id="notifications-email"
                        type="checkbox"
                        className="custom-control-input"
                        name="notifications.emailAlerts"
                        checked={config.notifications.emailAlerts}
                        onChange={handleInputChange}
                      />
                      <label className="custom-control-label" htmlFor="notifications-email">
                        Enviar alertas por e-mail para falhas de importação
                      </label>
                    </div>
                  </div>
                  <div className="col-12">
                    <label htmlFor="notifications-webhook" className="form-label text-uppercase small text-muted">
                      Webhook (opcional)
                    </label>
                    <input
                      id="notifications-webhook"
                      type="url"
                      className="form-control"
                      name="notifications.webhookUrl"
                      value={config.notifications.webhookUrl ?? ''}
                      placeholder="https://exemplo.com/webhook"
                      onChange={handleInputChange}
                    />
                    <small className="text-muted">URLs vazias desativam o envio para webhook.</small>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="card-footer d-flex flex-column flex-md-row justify-content-end gap-2">
              <button type="button" className="btn btn-outline-secondary" onClick={handleReset} disabled={!hasChanges || saving}>
                Reverter
              </button>
              <button type="submit" className="btn btn-primary" disabled={!hasChanges || saving}>
                {saving ? (
                  <span className="d-inline-flex align-items-center gap-2">
                    <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                    Salvando…
                  </span>
                ) : (
                  'Salvar configurações'
                )}
              </button>
            </div>
          </div>
        </form>
      ) : null}
    </section>
  );
}
