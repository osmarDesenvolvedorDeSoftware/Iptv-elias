import { Dispatch, SetStateAction, useCallback, useEffect, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import {
  getConfig,
  getConfigSchema,
  resetConfig,
  saveConfig,
  testConfig,
} from '../data/services/configService';
import { ConfigSchema, ConfigTestResponse, GeneralSettings, SaveConfigPayload } from '../data/types';

interface UseConfigResult {
  config: GeneralSettings | null;
  schema: ConfigSchema | null;
  loading: boolean;
  error: string | null;
  saving: boolean;
  testing: boolean;
  resetting: boolean;
  reload: () => Promise<void>;
  save: (payload: SaveConfigPayload) => Promise<GeneralSettings>;
  testConnection: (payload: Partial<SaveConfigPayload>) => Promise<ConfigTestResponse>;
  reset: () => Promise<GeneralSettings>;
  setConfig: Dispatch<SetStateAction<GeneralSettings | null>>;
}

export function useConfig(): UseConfigResult {
  const [config, setConfig] = useState<GeneralSettings | null>(null);
  const [schema, setSchema] = useState<ConfigSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [resetting, setResetting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [schemaResponse, configResponse] = await Promise.all([getConfigSchema(), getConfig()]);
      setSchema(schemaResponse);
      setConfig(configResponse);
      setError(null);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Erro ao carregar configurações.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = useCallback(async (payload: SaveConfigPayload) => {
    setSaving(true);
    try {
      const saved = await saveConfig(payload);
      setConfig(saved);
      return saved;
    } finally {
      setSaving(false);
    }
  }, []);

  const testConnection = useCallback(async (payload: Partial<SaveConfigPayload>) => {
    setTesting(true);
    try {
      const result = await testConfig(payload);
      setConfig((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          lastTestStatus: result.status,
          lastTestMessage: result.message,
          lastTestAt: result.testedAt ?? prev.lastTestAt,
        };
      });
      return result;
    } finally {
      setTesting(false);
    }
  }, []);

  const reset = useCallback(async () => {
    setResetting(true);
    try {
      const fresh = await resetConfig();
      setConfig(fresh);
      return fresh;
    } finally {
      setResetting(false);
    }
  }, []);

  return {
    config,
    schema,
    loading,
    error,
    saving,
    testing,
    resetting,
    reload: load,
    save,
    testConnection,
    reset,
    setConfig,
  };
}
