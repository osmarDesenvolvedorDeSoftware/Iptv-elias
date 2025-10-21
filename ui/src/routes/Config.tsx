import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { ConfigForm, ConfigFormState } from '../components/config/ConfigForm';
import { ConfigStatusCard } from '../components/config/ConfigStatusCard';
import { getBouquets } from '../data/services/bouquetService';
import { Bouquet, GeneralSettings, SaveConfigPayload } from '../data/types';
import type { ApiError } from '../data/adapters/ApiAdapter';
import { useConfig } from '../hooks/useConfig';
import { useToast } from '../providers/ToastProvider';
import {
  extractDbSslMisconfigMessage,
  extractDbSslMisconfigMessageFromApiError,
} from '../utils/dbErrors';

function createFormState(config: GeneralSettings): ConfigFormState {
  return {
    dbHost: config.dbHost ?? '',
    dbPort: String(config.dbPort ?? 3306),
    dbUser: config.dbUser ?? '',
    dbName: config.dbName ?? '',
    apiBaseUrl: config.apiBaseUrl ?? '',
    m3uLink: config.m3uLink ?? '',
    xtreamUser: config.xtreamUser ?? '',
    useXtreamApi: config.useXtreamApi,
    bouquetNormal: config.bouquetNormal !== null && config.bouquetNormal !== undefined ? String(config.bouquetNormal) : '',
    bouquetAdulto: config.bouquetAdulto !== null && config.bouquetAdulto !== undefined ? String(config.bouquetAdulto) : '',
    ignoredPrefixes: [...(config.ignoredPrefixes ?? [])],
    dbPass: '',
    dbPassMasked: config.dbPassMasked,
    dbPassTouched: false,
    xtreamPass: '',
    xtreamPassMasked: config.xtreamPassMasked,
    xtreamPassTouched: false,
    tmdbKey: '',
    tmdbKeyMasked: config.tmdbKeyMasked,
    tmdbKeyTouched: false,
    lastTestStatus: config.lastTestStatus,
    lastTestMessage: config.lastTestMessage,
    lastTestAt: config.lastTestAt,
  };
}

function buildPayload(form: ConfigFormState): SaveConfigPayload {
  const port = Number.parseInt(form.dbPort, 10);
  const bouquetNormal = form.bouquetNormal ? Number(form.bouquetNormal) : null;
  const bouquetAdulto = form.bouquetAdulto ? Number(form.bouquetAdulto) : null;
  const prefixes = form.ignoredPrefixes.map((prefix) => prefix.trim()).filter((prefix) => prefix.length > 0);

  return {
    dbHost: form.dbHost.trim(),
    dbPort: Number.isFinite(port) ? port : 0,
    dbUser: form.dbUser.trim(),
    dbName: form.dbName.trim(),
    apiBaseUrl: form.apiBaseUrl.trim(),
    m3uLink: form.m3uLink.trim(),
    tmdbKey: form.tmdbKeyTouched ? form.tmdbKey.trim() : null,
    xtreamUser: form.xtreamUser.trim(),
    useXtreamApi: form.useXtreamApi,
    bouquetNormal,
    bouquetAdulto,
    ignoredPrefixes: prefixes,
    dbPass: form.dbPassTouched ? form.dbPass : null,
    xtreamPass: form.xtreamPassTouched ? form.xtreamPass : null,
  };
}

export default function Configuracoes() {
  const { push } = useToast();
  const { config, loading, error, saving, testing, resetting, reload, save, testConnection, reset } = useConfig();
  const [form, setForm] = useState<ConfigFormState | null>(null);
  const [bouquets, setBouquets] = useState<Bouquet[]>([]);
  const [bouquetsLoading, setBouquetsLoading] = useState(false);
  const [bouquetError, setBouquetError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadBouquets() {
      setBouquetsLoading(true);
      try {
        const response = await getBouquets();
        if (isMounted) {
          setBouquets(response.bouquets);
          setBouquetError(null);
        }
      } catch (err) {
        if (isMounted) {
          const apiError = err as ApiError;
          setBouquetError(apiError?.message ?? 'Erro ao carregar bouquets disponíveis.');
        }
      } finally {
        if (isMounted) {
          setBouquetsLoading(false);
        }
      }
    }

    loadBouquets();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!config) {
      return;
    }

    setForm((current) => {
      if (!current) {
        return createFormState(config);
      }

      return {
        ...current,
        dbPassMasked: config.dbPassMasked,
        xtreamPassMasked: config.xtreamPassMasked,
        tmdbKeyMasked: config.tmdbKeyMasked,
        lastTestStatus: config.lastTestStatus,
        lastTestMessage: config.lastTestMessage,
        lastTestAt: config.lastTestAt,
      };
    });
  }, [config]);

  const handleChange = useCallback((changes: Partial<ConfigFormState>) => {
    setForm((current) => (current ? { ...current, ...changes } : current));
  }, []);

  const handleDbPassChange = useCallback((value: string) => {
    setForm((current) => (current ? { ...current, dbPass: value, dbPassTouched: true } : current));
  }, []);

  const handleXtreamPassChange = useCallback((value: string) => {
    setForm((current) => (current ? { ...current, xtreamPass: value, xtreamPassTouched: true } : current));
  }, []);

  const handleTmdbKeyChange = useCallback((value: string) => {
    setForm((current) => (current ? { ...current, tmdbKey: value, tmdbKeyTouched: true } : current));
  }, []);

  const handlePrefixAdd = useCallback((prefix: string) => {
    setForm((current) => {
      if (!current) {
        return current;
      }

      const normalized = prefix.trim();
      if (!normalized) {
        return current;
      }

      const exists = current.ignoredPrefixes.some((value) => value.toLowerCase() === normalized.toLowerCase());
      if (exists) {
        return current;
      }

      return {
        ...current,
        ignoredPrefixes: [...current.ignoredPrefixes, normalized],
      };
    });
  }, []);

  const handlePrefixRemove = useCallback((prefix: string) => {
    setForm((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        ignoredPrefixes: current.ignoredPrefixes.filter((value) => value !== prefix),
      };
    });
  }, []);

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!form) {
        return;
      }

      try {
        const payload = buildPayload(form);
        const saved = await save(payload);
        setForm(createFormState(saved));
        push('Configurações salvas com sucesso.', 'success');
      } catch (err) {
        const apiError = err as ApiError;
        push(apiError?.message ?? 'Não foi possível salvar as configurações.', 'error');
      }
    },
    [form, save, push],
  );

  const handleTestConnection = useCallback(async () => {
    if (!form) {
      return;
    }

    try {
      const payload = buildPayload(form);
      const result = await testConnection(payload);
      const sslMessage = extractDbSslMisconfigMessage(result);

      if (result.success) {
        push(result.message || 'Conexão validada com sucesso.', 'success');
      } else if (sslMessage) {
        push(`⚠️ ${sslMessage}`, 'error');
      } else {
        push(result.message || 'Falha ao testar conexão.', 'error');
      }
    } catch (err) {
      const apiError = err as ApiError;
      const sslMessage = extractDbSslMisconfigMessageFromApiError(apiError);

      if (sslMessage) {
        push(`⚠️ ${sslMessage}`, 'error');
      } else {
        push(apiError?.message ?? 'Erro ao testar conexão.', 'error');
      }
    }
  }, [form, testConnection, push]);

  const handleReset = useCallback(async () => {
    try {
      const fresh = await reset();
      setForm(createFormState(fresh));
      push('Configurações restauradas para os padrões.', 'info');
    } catch (err) {
      const apiError = err as ApiError;
      push(apiError?.message ?? 'Erro ao restaurar padrões.', 'error');
    }
  }, [reset, push]);

  const statusData = useMemo(() => {
    if (!form) {
      return null;
    }

    const portNumber = Number.parseInt(form.dbPort, 10);
    const tmdbConfigured = form.tmdbKeyMasked || (form.tmdbKeyTouched && form.tmdbKey.trim().length > 0);
    const xtreamConfigured = form.xtreamPassMasked || (form.xtreamPassTouched && form.xtreamPass.trim().length > 0);

    return {
      database: {
        host: form.dbHost,
        port: Number.isFinite(portNumber) ? portNumber : null,
        name: form.dbName,
      },
      status: form.lastTestStatus,
      message: form.lastTestMessage,
      testedAt: form.lastTestAt,
      tmdbConfigured,
      xtreamConfigured,
      useXtreamApi: form.useXtreamApi,
    };
  }, [form]);

  if (loading || !form) {
    return (
      <div className="container py-5 text-center">
        <div className="spinner-border text-primary mb-3" role="status" aria-hidden="true" />
        <p className="mb-0 fw-semibold">Carregando configurações…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container py-5 text-center">
        <p className="text-danger mb-3 fw-semibold">{error}</p>
        <button type="button" className="btn btn-primary" onClick={reload}>
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div className="container py-4 d-flex flex-column gap-4">
      <header>
        <h1 className="h3 fw-semibold mb-1">Configurações</h1>
        <p className="text-muted mb-0">Gerencie credenciais, listas M3U, TMDb e bouquets diretamente pelo painel.</p>
      </header>

      <div className="row g-4">
        <div className="col-12 col-lg-8">
          <ConfigForm
            form={form}
            onChange={handleChange}
            onDbPassChange={handleDbPassChange}
            onXtreamPassChange={handleXtreamPassChange}
            onTmdbKeyChange={handleTmdbKeyChange}
            onIgnoredPrefixAdd={handlePrefixAdd}
            onIgnoredPrefixRemove={handlePrefixRemove}
            onSubmit={handleSubmit}
            onTestConnection={handleTestConnection}
            onReset={handleReset}
            saving={saving}
            testing={testing}
            resetting={resetting}
            disabled={loading}
            bouquets={bouquets}
            bouquetsLoading={bouquetsLoading}
            bouquetError={bouquetError}
          />
        </div>

        <div className="col-12 col-lg-4">
          {statusData ? (
            <ConfigStatusCard
              database={statusData.database}
              status={statusData.status}
              message={statusData.message}
              testedAt={statusData.testedAt}
              testing={testing}
              tmdbConfigured={statusData.tmdbConfigured}
              xtreamConfigured={statusData.xtreamConfigured}
              useXtreamApi={statusData.useXtreamApi}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
