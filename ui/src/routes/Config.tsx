import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { getConfig, saveConfig } from '../data/services/configService';
import { getXuiIntegrationConfig, saveXuiIntegrationConfig } from '../data/services/integrationService';
import { ConfigResponse, XuiIntegrationConfig } from '../data/types';
import { useToast } from '../providers/ToastProvider';

type TabKey = 'importer' | 'tmdb' | 'notifications' | 'xui';

type InputEvent = ChangeEvent<HTMLInputElement | HTMLSelectElement>;

const tabLabels: Record<TabKey, string> = {
  importer: 'Importador',
  tmdb: 'TMDb',
  notifications: 'Notificações',
  xui: 'Integração XUI',
};

function cloneConfig(config: ConfigResponse): ConfigResponse {
  return JSON.parse(JSON.stringify(config));
}

function normalizeConfig(config: ConfigResponse): ConfigResponse {
  const defaultCategories = Array.isArray(config.importer?.defaultCategories)
    ? config.importer.defaultCategories.filter(
        (category): category is string => typeof category === 'string' && category.trim().length > 0,
      )
    : [];

  return {
    ...config,
    importer: {
      ...config.importer,
      defaultCategories,
    },
  };
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

function parseNumericValue(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function cloneIntegration(config: XuiIntegrationConfig): XuiIntegrationConfig {
  return JSON.parse(JSON.stringify(config));
}

export default function Configuracoes() {
  const { push } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [initialConfig, setInitialConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('importer');
  const [saving, setSaving] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [restartRequired, setRestartRequired] = useState(false);
  const importerFirstFieldRef = useRef<HTMLInputElement>(null);
  const tmdbFirstFieldRef = useRef<HTMLInputElement>(null);
  const notificationsFirstFieldRef = useRef<HTMLInputElement>(null);
  const [integrationConfig, setIntegrationConfig] = useState<XuiIntegrationConfig | null>(null);
  const [initialIntegrationConfig, setInitialIntegrationConfig] = useState<XuiIntegrationConfig | null>(null);
  const [integrationLoading, setIntegrationLoading] = useState(true);
  const [integrationError, setIntegrationError] = useState<string | null>(null);
  const [integrationSaving, setIntegrationSaving] = useState(false);
  const [integrationRestartRequired, setIntegrationRestartRequired] = useState(false);
  const [moviesMappingText, setMoviesMappingText] = useState('');
  const [initialMoviesMappingText, setInitialMoviesMappingText] = useState('');
  const [seriesMappingText, setSeriesMappingText] = useState('');
  const [initialSeriesMappingText, setInitialSeriesMappingText] = useState('');
  const [adultKeywordsText, setAdultKeywordsText] = useState('');
  const [initialAdultKeywordsText, setInitialAdultKeywordsText] = useState('');
  const [adultCategoriesText, setAdultCategoriesText] = useState('');
  const [initialAdultCategoriesText, setInitialAdultCategoriesText] = useState('');
  const [integrationPassword, setIntegrationPassword] = useState('');
  const [clearIntegrationPassword, setClearIntegrationPassword] = useState(false);
  const [integrationValidationError, setIntegrationValidationError] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
    loadIntegration();
  }, []);

  useEffect(() => {
    if (!config || loading) {
      return;
    }

    const focusTargets = {
      importer: importerFirstFieldRef.current,
      tmdb: tmdbFirstFieldRef.current,
      notifications: notificationsFirstFieldRef.current,
      xui: null,
    } satisfies Record<TabKey, HTMLInputElement | null>;

    focusTargets[activeTab]?.focus();
  }, [activeTab, config, loading]);

  useEffect(() => {
    const tabParam = (searchParams.get('tab') ?? '').toLowerCase();
    if (tabParam && tabParam in tabLabels) {
      setActiveTab(tabParam as TabKey);
    }
  }, [searchParams]);

  const hasChanges = useMemo(() => {
    if (!config || !initialConfig) {
      return false;
    }

    return JSON.stringify(config) !== JSON.stringify(initialConfig);
  }, [config, initialConfig]);

  const hasIntegrationChanges = useMemo(() => {
    if (!integrationConfig || !initialIntegrationConfig) {
      return false;
    }

    const baseChanged = JSON.stringify(integrationConfig) !== JSON.stringify(initialIntegrationConfig);

    return (
      baseChanged ||
      moviesMappingText !== initialMoviesMappingText ||
      seriesMappingText !== initialSeriesMappingText ||
      adultKeywordsText !== initialAdultKeywordsText ||
      adultCategoriesText !== initialAdultCategoriesText ||
      integrationPassword.trim().length > 0 ||
      clearIntegrationPassword
    );
  }, [
    integrationConfig,
    initialIntegrationConfig,
    moviesMappingText,
    initialMoviesMappingText,
    seriesMappingText,
    initialSeriesMappingText,
    adultKeywordsText,
    initialAdultKeywordsText,
    adultCategoriesText,
    initialAdultCategoriesText,
    integrationPassword,
    clearIntegrationPassword,
  ]);

  const defaultCategoriesText = useMemo(() => {
    if (!config) {
      return '';
    }

    const categories = Array.isArray(config.importer?.defaultCategories)
      ? config.importer.defaultCategories
      : [];

    return categories.join(', ');
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
      const normalized = normalizeConfig(response);
      setConfig(cloneConfig(normalized));
      setInitialConfig(cloneConfig(normalized));
      setRestartRequired(false);
      setShowErrors(false);
    } catch (loadError) {
      const apiError = loadError as ApiError;
      setError(apiError?.message ?? 'Não foi possível carregar as configurações.');
    } finally {
      setLoading(false);
    }
  }

  async function loadIntegration() {
    setIntegrationLoading(true);
    setIntegrationError(null);

    try {
      const response = await getXuiIntegrationConfig();
      const normalized = cloneIntegration(response);
      setIntegrationConfig(normalized);
      setInitialIntegrationConfig(cloneIntegration(response));

      const moviesText = JSON.stringify(response.options?.categoryMapping?.movies ?? {}, null, 2);
      const seriesText = JSON.stringify(response.options?.categoryMapping?.series ?? {}, null, 2);
      const keywordsText = (response.options?.adultKeywords ?? []).join(', ');
      const categoriesText = (response.options?.adultCategories ?? [])
        .map((category) => String(category))
        .join(', ');

      setMoviesMappingText(moviesText);
      setInitialMoviesMappingText(moviesText);
      setSeriesMappingText(seriesText);
      setInitialSeriesMappingText(seriesText);
      setAdultKeywordsText(keywordsText);
      setInitialAdultKeywordsText(keywordsText);
      setAdultCategoriesText(categoriesText);
      setInitialAdultCategoriesText(categoriesText);
      setIntegrationPassword('');
      setClearIntegrationPassword(false);
      setIntegrationValidationError(null);
      setIntegrationRestartRequired(false);
    } catch (loadError) {
      const apiError = loadError as ApiError;
      setIntegrationError(apiError?.message ?? 'Não foi possível carregar a integração XUI.');
    } finally {
      setIntegrationLoading(false);
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

  function handleIntegrationFieldChange(event: InputEvent) {
    if (!integrationConfig) {
      return;
    }

    const { name, value, type, checked } = event.target;

    setIntegrationConfig((current) => {
      if (!current) {
        return current;
      }

      const next: XuiIntegrationConfig = {
        ...current,
        options: {
          ...current.options,
          tmdb: { ...current.options.tmdb },
          bouquets: { ...current.options.bouquets },
          retry: { ...current.options.retry },
        },
      };

      switch (name) {
        case 'xuiDbUri':
          next.xuiDbUri = value;
          break;
        case 'xtreamBaseUrl':
          next.xtreamBaseUrl = value;
          break;
        case 'xtreamUsername':
          next.xtreamUsername = value;
          break;
        case 'options.tmdb.enabled':
          next.options.tmdb.enabled = type === 'checkbox' ? checked : value === 'true';
          break;
        case 'options.tmdb.apiKey':
          next.options.tmdb.apiKey = value;
          break;
        case 'options.tmdb.language':
          next.options.tmdb.language = value;
          break;
        case 'options.tmdb.region':
          next.options.tmdb.region = value.toUpperCase();
          break;
        case 'options.throttleMs': {
          const numeric = Number(value);
          next.options.throttleMs = Number.isFinite(numeric) && numeric >= 0 ? numeric : 0;
          break;
        }
        case 'options.limitItems': {
          const numeric = parseNumericValue(value);
          next.options.limitItems = numeric;
          break;
        }
        case 'options.maxParallel': {
          const numeric = Number(value);
          next.options.maxParallel = Number.isFinite(numeric) && numeric >= 1 ? Math.floor(numeric) : 1;
          break;
        }
        case 'options.bouquets.movies':
          next.options.bouquets.movies = parseNumericValue(value);
          break;
        case 'options.bouquets.series':
          next.options.bouquets.series = parseNumericValue(value);
          break;
        case 'options.bouquets.adult':
          next.options.bouquets.adult = parseNumericValue(value);
          break;
        case 'options.retry.maxAttempts': {
          const numeric = Number(value);
          next.options.retry.maxAttempts = Number.isFinite(numeric) && numeric >= 1 ? Math.floor(numeric) : 1;
          break;
        }
        case 'options.retry.backoffSeconds': {
          const numeric = Number(value);
          next.options.retry.backoffSeconds = Number.isFinite(numeric) && numeric >= 1 ? Math.floor(numeric) : 1;
          break;
        }
        default:
          return current;
      }

      return next;
    });
  }

  function handleDefaultCategoriesChange(event: ChangeEvent<HTMLInputElement>) {
    const categories = event.target.value
      .split(',')
      .map((category) => category.trim())
      .filter((category): category is string => Boolean(category));

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
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (tab === 'importer') {
        next.delete('tab');
      } else {
        next.set('tab', tab);
      }
      return next;
    });
  }

  function handleReset() {
    if (!initialConfig) {
      return;
    }

    setConfig(cloneConfig(initialConfig));
    setShowErrors(false);
    setRestartRequired(false);
  }

  function handleIntegrationReset() {
    if (!initialIntegrationConfig) {
      return;
    }

    const cloned = cloneIntegration(initialIntegrationConfig);
    setIntegrationConfig(cloned);
    setMoviesMappingText(initialMoviesMappingText);
    setSeriesMappingText(initialSeriesMappingText);
    setAdultKeywordsText(initialAdultKeywordsText);
    setAdultCategoriesText(initialAdultCategoriesText);
    setIntegrationPassword('');
    setClearIntegrationPassword(false);
    setIntegrationValidationError(null);
    setIntegrationRestartRequired(false);
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
      const apiError = saveError as ApiError;
      push(apiError?.message ?? 'Erro ao salvar as configurações.', 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleIntegrationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!integrationConfig) {
      return;
    }

    setIntegrationValidationError(null);

    let moviesMapping: Record<string, number | string> = {};
    let seriesMapping: Record<string, number | string> = {};

    try {
      moviesMapping = moviesMappingText.trim() ? (JSON.parse(moviesMappingText) as Record<string, number | string>) : {};
      seriesMapping = seriesMappingText.trim() ? (JSON.parse(seriesMappingText) as Record<string, number | string>) : {};
      if (Array.isArray(moviesMapping) || typeof moviesMapping !== 'object') {
        throw new Error('invalid-mapping');
      }
      if (Array.isArray(seriesMapping) || typeof seriesMapping !== 'object') {
        throw new Error('invalid-mapping');
      }
    } catch (parseError) {
      setIntegrationValidationError('Mapeamentos de categorias devem ser objetos JSON válidos.');
      return;
    }

    const adultKeywords = adultKeywordsText
      .split(',')
      .map((keyword) => keyword.trim())
      .filter((keyword) => keyword.length > 0);
    const adultCategories = adultCategoriesText
      .split(',')
      .map((category) => category.trim())
      .filter((category) => category.length > 0)
      .map((category) => {
        const numeric = Number(category);
        return Number.isFinite(numeric) ? numeric : category;
      });

    const options = {
      ...integrationConfig.options,
      categoryMapping: {
        movies: moviesMapping,
        series: seriesMapping,
      },
      adultKeywords,
      adultCategories,
      bouquets: {
        movies: parseNumericValue(String(integrationConfig.options.bouquets.movies ?? '')),
        series: parseNumericValue(String(integrationConfig.options.bouquets.series ?? '')),
        adult: parseNumericValue(String(integrationConfig.options.bouquets.adult ?? '')),
      },
      retry: {
        ...integrationConfig.options.retry,
        maxAttempts: Math.max(1, Math.floor(integrationConfig.options.retry.maxAttempts ?? 1)),
        backoffSeconds: Math.max(1, Math.floor(integrationConfig.options.retry.backoffSeconds ?? 1)),
      },
      throttleMs: Math.max(0, integrationConfig.options.throttleMs ?? 0),
      limitItems:
        integrationConfig.options.limitItems === null || integrationConfig.options.limitItems === undefined
          ? null
          : Math.max(0, Number(integrationConfig.options.limitItems)),
      maxParallel: Math.max(1, Math.floor(integrationConfig.options.maxParallel ?? 1)),
    };

    const payload: Partial<XuiIntegrationConfig> & { xtreamPassword?: string | null; options: typeof options } = {
      xuiDbUri: integrationConfig.xuiDbUri?.trim() || null,
      xtreamBaseUrl: integrationConfig.xtreamBaseUrl?.trim() || null,
      xtreamUsername: integrationConfig.xtreamUsername?.trim() || null,
      options,
    };

    if (integrationPassword.trim()) {
      payload.xtreamPassword = integrationPassword.trim();
    } else if (clearIntegrationPassword) {
      payload.xtreamPassword = '';
    }

    setIntegrationSaving(true);

    try {
      const response = await saveXuiIntegrationConfig(payload);
      const updated = cloneIntegration(response.config);
      setIntegrationConfig(updated);
      setInitialIntegrationConfig(cloneIntegration(response.config));

      const updatedMovies = JSON.stringify(updated.options.categoryMapping.movies ?? {}, null, 2);
      const updatedSeries = JSON.stringify(updated.options.categoryMapping.series ?? {}, null, 2);
      const updatedKeywords = (updated.options.adultKeywords ?? []).join(', ');
      const updatedCategories = (updated.options.adultCategories ?? [])
        .map((category) => String(category))
        .join(', ');

      setMoviesMappingText(updatedMovies);
      setInitialMoviesMappingText(updatedMovies);
      setSeriesMappingText(updatedSeries);
      setInitialSeriesMappingText(updatedSeries);
      setAdultKeywordsText(updatedKeywords);
      setInitialAdultKeywordsText(updatedKeywords);
      setAdultCategoriesText(updatedCategories);
      setInitialAdultCategoriesText(updatedCategories);
      setIntegrationPassword('');
      setClearIntegrationPassword(false);
      setIntegrationValidationError(null);
      setIntegrationRestartRequired(response.requiresWorkerRestart);
      push('Integração XUI salva com sucesso', 'success');
    } catch (saveError) {
      const apiError = saveError as ApiError;
      push(apiError?.message ?? 'Erro ao salvar a integração XUI.', 'error');
    } finally {
      setIntegrationSaving(false);
    }
  }

  function renderGeneralContent() {
    if (!config) {
      return null;
    }

    return (
      <form onSubmit={handleSubmit}>
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
                  ref={importerFirstFieldRef}
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
                  ref={tmdbFirstFieldRef}
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
                {tmdbErrors.region ? <div className="invalid-feedback">Informe a região (ex.: BR).</div> : null}
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
                    ref={notificationsFirstFieldRef}
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
      </form>
    );
  }

  function renderIntegrationContent() {
    if (integrationLoading) {
      return (
        <div className="card-body" aria-busy="true">
          <div className="placeholder-glow">
            <div className="placeholder col-12 mb-3" style={{ height: '1.75rem' }} />
            <div className="placeholder col-10 mb-3" style={{ height: '1.75rem' }} />
            <div className="placeholder col-8" style={{ height: '1.75rem' }} />
          </div>
        </div>
      );
    }

    if (integrationError) {
      return (
        <div className="card-body">
          <div className="alert alert-danger d-flex flex-column flex-md-row align-items-md-center justify-content-between" role="alert">
            <span>{integrationError}</span>
            <button type="button" className="btn btn-outline-light mt-3 mt-md-0" onClick={loadIntegration}>
              Tentar novamente
            </button>
          </div>
        </div>
      );
    }

    if (!integrationConfig) {
      return <div className="card-body">Configuração não disponível.</div>;
    }

    return (
      <form onSubmit={handleIntegrationSubmit}>
        <div className="card-body">
          {integrationRestartRequired ? (
            <div className="alert alert-warning" role="alert">
              Alterações aplicadas exigem reinício do worker de importação.
            </div>
          ) : null}
          {integrationValidationError ? (
            <div className="alert alert-danger" role="alert">
              {integrationValidationError}
            </div>
          ) : null}

          <div className="row g-4">
            <div className="col-12 col-md-4">
              <label htmlFor="integration-xui-uri" className="form-label text-uppercase small text-muted">
                URI do banco XUI
              </label>
              <input
                id="integration-xui-uri"
                type="text"
                className="form-control"
                name="xuiDbUri"
                value={integrationConfig.xuiDbUri ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-xtream-base" className="form-label text-uppercase small text-muted">
                Xtream Base URL
              </label>
              <input
                id="integration-xtream-base"
                type="text"
                className="form-control"
                name="xtreamBaseUrl"
                value={integrationConfig.xtreamBaseUrl ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-xtream-user" className="form-label text-uppercase small text-muted">
                Xtream Usuário
              </label>
              <input
                id="integration-xtream-user"
                type="text"
                className="form-control"
                name="xtreamUsername"
                value={integrationConfig.xtreamUsername ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-xtream-pass" className="form-label text-uppercase small text-muted">
                Xtream Senha
              </label>
              <input
                id="integration-xtream-pass"
                type="password"
                className="form-control"
                value={integrationPassword}
                placeholder={integrationConfig.hasXtreamPassword ? '••••••••' : ''}
                onChange={(event) => setIntegrationPassword(event.target.value)}
              />
              <div className="form-text">Deixe em branco para manter a senha atual.</div>
              <div className="form-check mt-2">
                <input
                  id="integration-clear-pass"
                  className="form-check-input"
                  type="checkbox"
                  checked={clearIntegrationPassword}
                  onChange={(event) => setClearIntegrationPassword(event.target.checked)}
                />
                <label className="form-check-label" htmlFor="integration-clear-pass">
                  Limpar senha ao salvar
                </label>
              </div>
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-throttle" className="form-label text-uppercase small text-muted">
                Delay entre chamadas (ms)
              </label>
              <input
                id="integration-throttle"
                type="number"
                min={0}
                className="form-control"
                name="options.throttleMs"
                value={integrationConfig.options.throttleMs ?? 0}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-limit" className="form-label text-uppercase small text-muted">
                Limite de itens (opcional)
              </label>
              <input
                id="integration-limit"
                type="number"
                min={0}
                className="form-control"
                name="options.limitItems"
                value={integrationConfig.options.limitItems ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-max-parallel" className="form-label text-uppercase small text-muted">
                Jobs paralelos
              </label>
              <input
                id="integration-max-parallel"
                type="number"
                min={1}
                className="form-control"
                name="options.maxParallel"
                value={integrationConfig.options.maxParallel ?? 1}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12">
              <div className="form-check form-switch">
                <input
                  id="integration-tmdb-enabled"
                  className="form-check-input"
                  type="checkbox"
                  name="options.tmdb.enabled"
                  checked={Boolean(integrationConfig.options.tmdb.enabled)}
                  onChange={handleIntegrationFieldChange}
                />
                <label className="form-check-label" htmlFor="integration-tmdb-enabled">
                  Usar dados do TMDb
                </label>
              </div>
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-tmdb-key" className="form-label text-uppercase small text-muted">
                TMDb API Key
              </label>
              <input
                id="integration-tmdb-key"
                type="text"
                className="form-control"
                name="options.tmdb.apiKey"
                value={integrationConfig.options.tmdb.apiKey ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-tmdb-language" className="form-label text-uppercase small text-muted">
                Idioma TMDb
              </label>
              <input
                id="integration-tmdb-language"
                type="text"
                className="form-control"
                name="options.tmdb.language"
                value={integrationConfig.options.tmdb.language ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-tmdb-region" className="form-label text-uppercase small text-muted">
                Região TMDb
              </label>
              <input
                id="integration-tmdb-region"
                type="text"
                maxLength={2}
                className="form-control"
                name="options.tmdb.region"
                value={integrationConfig.options.tmdb.region ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-bouquet-movies" className="form-label text-uppercase small text-muted">
                Bouquet filmes
              </label>
              <input
                id="integration-bouquet-movies"
                type="number"
                min={0}
                className="form-control"
                name="options.bouquets.movies"
                value={integrationConfig.options.bouquets.movies ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-bouquet-series" className="form-label text-uppercase small text-muted">
                Bouquet séries
              </label>
              <input
                id="integration-bouquet-series"
                type="number"
                min={0}
                className="form-control"
                name="options.bouquets.series"
                value={integrationConfig.options.bouquets.series ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-4">
              <label htmlFor="integration-bouquet-adult" className="form-label text-uppercase small text-muted">
                Bouquet adulto
              </label>
              <input
                id="integration-bouquet-adult"
                type="number"
                min={0}
                className="form-control"
                name="options.bouquets.adult"
                value={integrationConfig.options.bouquets.adult ?? ''}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-6">
              <label htmlFor="integration-adult-keywords" className="form-label text-uppercase small text-muted">
                Palavras-chave adultas
              </label>
              <input
                id="integration-adult-keywords"
                type="text"
                className="form-control"
                value={adultKeywordsText}
                placeholder="Separadas por vírgula"
                onChange={(event) => setAdultKeywordsText(event.target.value)}
              />
            </div>
            <div className="col-12 col-md-6">
              <label htmlFor="integration-adult-categories" className="form-label text-uppercase small text-muted">
                Categorias adultas (IDs)
              </label>
              <input
                id="integration-adult-categories"
                type="text"
                className="form-control"
                value={adultCategoriesText}
                placeholder="Separadas por vírgula"
                onChange={(event) => setAdultCategoriesText(event.target.value)}
              />
            </div>
            <div className="col-12">
              <label htmlFor="integration-movies-mapping" className="form-label text-uppercase small text-muted">
                Mapeamento categorias (filmes)
              </label>
              <textarea
                id="integration-movies-mapping"
                className="form-control"
                rows={6}
                value={moviesMappingText}
                onChange={(event) => setMoviesMappingText(event.target.value)}
              />
              <small className="text-muted">Informe um objeto JSON no formato {`{"apiId": xuiCategoryId}`}. Ex.: {`{"12": 5}`}</small>
            </div>
            <div className="col-12">
              <label htmlFor="integration-series-mapping" className="form-label text-uppercase small text-muted">
                Mapeamento categorias (séries)
              </label>
              <textarea
                id="integration-series-mapping"
                className="form-control"
                rows={6}
                value={seriesMappingText}
                onChange={(event) => setSeriesMappingText(event.target.value)}
              />
            </div>
            <div className="col-12 col-md-6">
              <label htmlFor="integration-retry-attempts" className="form-label text-uppercase small text-muted">
                Tentativas em falhas (API Xtream)
              </label>
              <input
                id="integration-retry-attempts"
                type="number"
                min={1}
                className="form-control"
                name="options.retry.maxAttempts"
                value={integrationConfig.options.retry.maxAttempts ?? 1}
                onChange={handleIntegrationFieldChange}
              />
            </div>
            <div className="col-12 col-md-6">
              <label htmlFor="integration-retry-backoff" className="form-label text-uppercase small text-muted">
                Backoff entre tentativas (s)
              </label>
              <input
                id="integration-retry-backoff"
                type="number"
                min={1}
                className="form-control"
                name="options.retry.backoffSeconds"
                value={integrationConfig.options.retry.backoffSeconds ?? 1}
                onChange={handleIntegrationFieldChange}
              />
            </div>
          </div>
        </div>
        <div className="card-footer d-flex flex-column flex-md-row justify-content-end gap-2">
          <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={handleIntegrationReset}
            disabled={!hasIntegrationChanges || integrationSaving}
          >
            Reverter
          </button>
          <button type="submit" className="btn btn-primary" disabled={!hasIntegrationChanges || integrationSaving}>
            {integrationSaving ? (
              <span className="d-inline-flex align-items-center gap-2">
                <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                Salvando…
              </span>
            ) : (
              'Salvar integração'
            )}
          </button>
        </div>
      </form>
    );
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
          {activeTab === 'xui' ? renderIntegrationContent() : renderGeneralContent()}
        </div>
      ) : null}
    </section>
  );
}
