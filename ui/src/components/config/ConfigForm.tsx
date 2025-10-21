import { FormEvent, KeyboardEvent, useMemo, useState } from 'react';

import { Bouquet, ConfigStatus } from '../../data/types';

export interface ConfigFormState {
  dbHost: string;
  dbPort: string;
  dbUser: string;
  dbName: string;
  apiBaseUrl: string;
  m3uLink: string;
  xtreamUser: string;
  useXtreamApi: boolean;
  bouquetNormal: string;
  bouquetAdulto: string;
  ignoredPrefixes: string[];
  dbPass: string;
  dbPassMasked: boolean;
  dbPassTouched: boolean;
  xtreamPass: string;
  xtreamPassMasked: boolean;
  xtreamPassTouched: boolean;
  tmdbKey: string;
  tmdbKeyMasked: boolean;
  tmdbKeyTouched: boolean;
  lastTestStatus: ConfigStatus;
  lastTestMessage: string | null;
  lastTestAt: string | null;
}

export interface ConfigFormProps {
  form: ConfigFormState;
  onChange: (changes: Partial<ConfigFormState>) => void;
  onDbPassChange: (value: string) => void;
  onXtreamPassChange: (value: string) => void;
  onTmdbKeyChange: (value: string) => void;
  onIgnoredPrefixAdd: (prefix: string) => void;
  onIgnoredPrefixRemove: (prefix: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTestConnection: () => void;
  onReset: () => void;
  saving: boolean;
  testing: boolean;
  resetting: boolean;
  disabled?: boolean;
  bouquets: Bouquet[];
  bouquetsLoading: boolean;
  bouquetError: string | null;
}

function renderSecretHelper(masked: boolean, touched: boolean): string | null {
  if (!masked) {
    return null;
  }
  if (touched) {
    return 'O valor será atualizado ao salvar.';
  }
  return 'Mantendo valor atual. Preencha para substituir.';
}

export function ConfigForm({
  form,
  onChange,
  onDbPassChange,
  onXtreamPassChange,
  onTmdbKeyChange,
  onIgnoredPrefixAdd,
  onIgnoredPrefixRemove,
  onSubmit,
  onTestConnection,
  onReset,
  saving,
  testing,
  resetting,
  disabled,
  bouquets,
  bouquetsLoading,
  bouquetError,
}: ConfigFormProps) {
  const [prefixDraft, setPrefixDraft] = useState('');

  const hasDirtySecrets = useMemo(() => {
    return form.dbPassTouched || form.xtreamPassTouched || form.tmdbKeyTouched;
  }, [form.dbPassTouched, form.xtreamPassTouched, form.tmdbKeyTouched]);

  function handleAddPrefix() {
    const value = prefixDraft.trim();
    if (!value) {
      return;
    }
    onIgnoredPrefixAdd(value);
    setPrefixDraft('');
  }

  function handlePrefixKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      handleAddPrefix();
    }
  }

  function renderPrefixes() {
    if (!form.ignoredPrefixes.length) {
      return <span className="text-muted">Nenhum prefixo adicionado.</span>;
    }

    return form.ignoredPrefixes.map((prefix) => (
      <span key={prefix} className="badge rounded-pill text-bg-secondary d-inline-flex align-items-center gap-2">
        {prefix}
        <button
          type="button"
          className="btn btn-sm btn-link text-decoration-none text-white"
          onClick={() => onIgnoredPrefixRemove(prefix)}
          aria-label={`Remover prefixo ${prefix}`}
        >
          ×
        </button>
      </span>
    ));
  }

  return (
    <form className="d-flex flex-column gap-4" onSubmit={onSubmit} noValidate>
      <div className="card shadow-sm">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-start mb-4">
            <div>
              <h5 className="card-title mb-1">Banco de Dados MySQL</h5>
              <p className="card-text text-muted mb-0">
                Defina as credenciais do banco do XUI. Teste a conexão antes de salvar mudanças.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-outline-primary"
              onClick={onTestConnection}
              disabled={testing || disabled}
            >
              {testing ? (
                <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
              ) : (
                <span className="me-2" aria-hidden="true">
                  🔌
                </span>
              )}
              Testar Conexão
            </button>
          </div>

          <div className="row g-3">
            <div className="col-md-6">
              <label htmlFor="dbHost" className="form-label fw-semibold">
                Host
              </label>
              <input
                id="dbHost"
                type="text"
                className="form-control"
                value={form.dbHost}
                onChange={(event) => onChange({ dbHost: event.target.value })}
                disabled={disabled}
                required
              />
            </div>

            <div className="col-md-2">
              <label htmlFor="dbPort" className="form-label fw-semibold">
                Porta
              </label>
              <input
                id="dbPort"
                type="number"
                className="form-control"
                min={1}
                max={65535}
                value={form.dbPort}
                onChange={(event) => onChange({ dbPort: event.target.value })}
                disabled={disabled}
                required
              />
            </div>

            <div className="col-md-4">
              <label htmlFor="dbName" className="form-label fw-semibold">
                Banco
              </label>
              <input
                id="dbName"
                type="text"
                className="form-control"
                value={form.dbName}
                onChange={(event) => onChange({ dbName: event.target.value })}
                disabled={disabled}
                required
              />
            </div>

            <div className="col-md-4">
              <label htmlFor="dbUser" className="form-label fw-semibold">
                Usuário
              </label>
              <input
                id="dbUser"
                type="text"
                className="form-control"
                value={form.dbUser}
                onChange={(event) => onChange({ dbUser: event.target.value })}
                disabled={disabled}
                required
              />
            </div>

            <div className="col-md-4">
              <label htmlFor="dbPass" className="form-label fw-semibold">
                Senha
              </label>
              <input
                id="dbPass"
                type="password"
                className="form-control"
                value={form.dbPass}
                placeholder={form.dbPassMasked && !form.dbPassTouched ? '••••••••' : ''}
                onChange={(event) => onDbPassChange(event.target.value)}
                disabled={disabled}
              />
              <div className="form-text">{renderSecretHelper(form.dbPassMasked, form.dbPassTouched)}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="card shadow-sm">
        <div className="card-body">
          <h5 className="card-title mb-3">Xtream &amp; Lista M3U</h5>
          <div className="row g-3">
            <div className="col-md-6">
              <label htmlFor="m3uLink" className="form-label fw-semibold">
                Link da Lista M3U
              </label>
              <input
                id="m3uLink"
                type="url"
                className="form-control"
                value={form.m3uLink}
                onChange={(event) => onChange({ m3uLink: event.target.value })}
                disabled={disabled}
                placeholder="http://exemplo.com/get.php?username=..."
              />
            </div>

            <div className="col-md-6">
              <label htmlFor="apiBaseUrl" className="form-label fw-semibold">
                URL Base da API Xtream
              </label>
              <input
                id="apiBaseUrl"
                type="url"
                className="form-control"
                value={form.apiBaseUrl}
                onChange={(event) => onChange({ apiBaseUrl: event.target.value })}
                disabled={disabled}
                placeholder="http://painel.exemplo.com"
              />
            </div>

            <div className="col-md-4">
              <label htmlFor="xtreamUser" className="form-label fw-semibold">
                Usuário Xtream
              </label>
              <input
                id="xtreamUser"
                type="text"
                className="form-control"
                value={form.xtreamUser}
                onChange={(event) => onChange({ xtreamUser: event.target.value })}
                disabled={disabled}
              />
            </div>

            <div className="col-md-4">
              <label htmlFor="xtreamPass" className="form-label fw-semibold">
                Senha Xtream
              </label>
              <input
                id="xtreamPass"
                type="password"
                className="form-control"
                value={form.xtreamPass}
                placeholder={form.xtreamPassMasked && !form.xtreamPassTouched ? '••••••••' : ''}
                onChange={(event) => onXtreamPassChange(event.target.value)}
                disabled={disabled}
              />
              <div className="form-text">{renderSecretHelper(form.xtreamPassMasked, form.xtreamPassTouched)}</div>
            </div>

            <div className="col-md-4 d-flex align-items-center">
              <div className="form-check mt-4">
                <input
                  id="useXtreamApi"
                  className="form-check-input"
                  type="checkbox"
                  checked={form.useXtreamApi}
                  onChange={(event) => onChange({ useXtreamApi: event.target.checked })}
                  disabled={disabled}
                />
                <label className="form-check-label" htmlFor="useXtreamApi">
                  Usar API Xtream
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card shadow-sm">
        <div className="card-body">
          <h5 className="card-title mb-3">TMDb &amp; Categorias</h5>
          <div className="row g-3">
            <div className="col-md-6">
              <label htmlFor="tmdbKey" className="form-label fw-semibold">
                Chave TMDb
              </label>
              <input
                id="tmdbKey"
                type="password"
                className="form-control"
                value={form.tmdbKey}
                placeholder={form.tmdbKeyMasked && !form.tmdbKeyTouched ? '••••••••' : ''}
                onChange={(event) => onTmdbKeyChange(event.target.value)}
                disabled={disabled}
              />
              <div className="form-text">{renderSecretHelper(form.tmdbKeyMasked, form.tmdbKeyTouched)}</div>
            </div>

            <div className="col-md-6">
              <label htmlFor="prefixInput" className="form-label fw-semibold">
                Prefixos Ignorados
              </label>
              <div className="input-group">
                <input
                  id="prefixInput"
                  type="text"
                  className="form-control"
                  value={prefixDraft}
                  onChange={(event) => setPrefixDraft(event.target.value)}
                  onKeyDown={handlePrefixKeyDown}
                  disabled={disabled}
                  placeholder="Ex.: Filmes"
                />
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={handleAddPrefix}
                  disabled={disabled}
                >
                  Adicionar
                </button>
              </div>
              <div className="d-flex gap-2 flex-wrap mt-2">{renderPrefixes()}</div>
            </div>

            <div className="col-md-6">
              <label htmlFor="bouquetNormal" className="form-label fw-semibold">
                Bouquet Normal
              </label>
              <select
                id="bouquetNormal"
                className="form-select"
                value={form.bouquetNormal}
                onChange={(event) => onChange({ bouquetNormal: event.target.value })}
                disabled={disabled || bouquetsLoading}
              >
                <option value="">Selecione um bouquet</option>
                {bouquets.map((bouquet) => (
                  <option key={bouquet.id} value={bouquet.id}>
                    {bouquet.name}
                  </option>
                ))}
              </select>
              {bouquetError ? <div className="form-text text-danger">{bouquetError}</div> : null}
            </div>

            <div className="col-md-6">
              <label htmlFor="bouquetAdulto" className="form-label fw-semibold">
                Bouquet Adulto
              </label>
              <select
                id="bouquetAdulto"
                className="form-select"
                value={form.bouquetAdulto}
                onChange={(event) => onChange({ bouquetAdulto: event.target.value })}
                disabled={disabled || bouquetsLoading}
              >
                <option value="">Selecione um bouquet</option>
                {bouquets.map((bouquet) => (
                  <option key={bouquet.id} value={bouquet.id}>
                    {bouquet.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="d-flex flex-column flex-md-row gap-2 justify-content-end">
        <button type="button" className="btn btn-outline-secondary" onClick={onReset} disabled={resetting || disabled}>
          {resetting ? (
            <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
          ) : (
            <span className="me-2" aria-hidden="true">
              ↺
            </span>
          )}
          Restaurar Padrões
        </button>

        <button type="submit" className="btn btn-primary" disabled={saving || disabled}>
          {saving ? (
            <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
          ) : (
            <span className="me-2" aria-hidden="true">
              💾
            </span>
          )}
          Salvar Configurações
        </button>
      </div>

      {hasDirtySecrets ? (
        <p className="text-muted small mb-0">
          Valores sensíveis serão criptografados no backend e não ficarão visíveis após o salvamento.
        </p>
      ) : null}
    </form>
  );
}
