import { useMemo } from 'react';

import type { AdminSettingsDetails, AdminUserConfigSnapshot } from '../../data/types';

interface UserConfigModalProps {
  open: boolean;
  config: AdminUserConfigSnapshot | null;
  loading?: boolean;
  resetting?: boolean;
  onClose: () => void;
  onReset: () => void;
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'Sim' : 'Não';
  }
  if (typeof value === 'number') {
    return value.toString();
  }
  return String(value);
}

function extractDatabase(settings: AdminSettingsDetails | null) {
  if (!settings) {
    return null;
  }
  return {
    host: settings.db_host ?? '—',
    port: settings.db_port ?? '—',
    user: settings.db_user ?? '—',
    name: settings.db_name ?? '—',
    password: settings.db_pass ?? '—',
  };
}

function extractIntegrations(settings: AdminSettingsDetails | null) {
  if (!settings) {
    return null;
  }
  return {
    apiBaseUrl: settings.api_base_url ?? '—',
    m3u: settings.m3u_link ?? '—',
    tmdbKey: settings.tmdb_key ?? '—',
    xtreamUser: settings.xtream_user ?? '—',
    xtreamPass: settings.xtream_pass ?? '—',
  };
}

export function UserConfigModal({ open, config, loading = false, resetting = false, onClose, onReset }: UserConfigModalProps) {
  const database = useMemo(() => extractDatabase(config?.settings ?? null), [config?.settings]);
  const integrations = useMemo(() => extractIntegrations(config?.settings ?? null), [config?.settings]);
  const panel = config?.panel ?? null;

  if (!open) {
    return null;
  }

  return (
    <>
      <div className="modal fade show" style={{ display: 'block' }} role="dialog" aria-modal="true">
        <div className="modal-dialog modal-lg modal-dialog-scrollable">
          <div className="modal-content">
            <div className="modal-header">
              <div>
                <h5 className="modal-title">Configurações IPTV</h5>
                {config ? (
                  <small className="text-muted">Tenant {config.tenant.name ?? config.tenant.id}</small>
                ) : null}
              </div>
              <button type="button" className="btn-close" onClick={onClose} aria-label="Fechar" />
            </div>
            <div className="modal-body">
              {loading ? (
                <div className="d-flex align-items-center gap-2">
                  <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                  <span>Carregando configurações…</span>
                </div>
              ) : null}

              {!loading && config ? (
                <div className="d-flex flex-column gap-4">
                  <section>
                    <h6 className="text-uppercase text-muted small">Banco de dados do painel</h6>
                    {database ? (
                      <dl className="row mb-0">
                        <dt className="col-sm-4">Host</dt>
                        <dd className="col-sm-8">{renderValue(database.host)}</dd>
                        <dt className="col-sm-4">Porta</dt>
                        <dd className="col-sm-8">{renderValue(database.port)}</dd>
                        <dt className="col-sm-4">Usuário</dt>
                        <dd className="col-sm-8">{renderValue(database.user)}</dd>
                        <dt className="col-sm-4">Banco</dt>
                        <dd className="col-sm-8">{renderValue(database.name)}</dd>
                        <dt className="col-sm-4">Senha</dt>
                        <dd className="col-sm-8"><code>{renderValue(database.password)}</code></dd>
                      </dl>
                    ) : (
                      <p className="text-muted mb-0">Nenhuma configuração de banco foi registrada ainda.</p>
                    )}
                  </section>

                  <section>
                    <h6 className="text-uppercase text-muted small">Integrações & Mídia</h6>
                    {integrations ? (
                      <dl className="row mb-0">
                        <dt className="col-sm-4">Endpoint API</dt>
                        <dd className="col-sm-8">{renderValue(integrations.apiBaseUrl)}</dd>
                        <dt className="col-sm-4">Lista M3U</dt>
                        <dd className="col-sm-8">{renderValue(integrations.m3u)}</dd>
                        <dt className="col-sm-4">TMDb Key</dt>
                        <dd className="col-sm-8"><code>{renderValue(integrations.tmdbKey)}</code></dd>
                        <dt className="col-sm-4">Xtream usuário</dt>
                        <dd className="col-sm-8">{renderValue(integrations.xtreamUser)}</dd>
                        <dt className="col-sm-4">Xtream senha</dt>
                        <dd className="col-sm-8"><code>{renderValue(integrations.xtreamPass)}</code></dd>
                      </dl>
                    ) : (
                      <p className="text-muted mb-0">Integrações externas não configuradas.</p>
                    )}
                  </section>

                  <section>
                    <h6 className="text-uppercase text-muted small">Painel XUI</h6>
                    {panel ? (
                      <dl className="row mb-0">
                        <dt className="col-sm-4">Domínio</dt>
                        <dd className="col-sm-8">{renderValue(panel.domain)}</dd>
                        <dt className="col-sm-4">Porta</dt>
                        <dd className="col-sm-8">{renderValue(panel.port)}</dd>
                        <dt className="col-sm-4">Usuário API</dt>
                        <dd className="col-sm-8">{renderValue(panel.username)}</dd>
                        <dt className="col-sm-4">Senha API</dt>
                        <dd className="col-sm-8"><code>{renderValue(panel.password)}</code></dd>
                        <dt className="col-sm-4">Ativo</dt>
                        <dd className="col-sm-8">{panel.active ? 'Sim' : 'Não'}</dd>
                        <dt className="col-sm-4">Última sincronização</dt>
                        <dd className="col-sm-8">{renderValue(panel.lastSync)}</dd>
                        <dt className="col-sm-4">URI Banco XUI</dt>
                        <dd className="col-sm-8">{renderValue(panel.xuiDbUri)}</dd>
                      </dl>
                    ) : (
                      <p className="text-muted mb-0">O painel XUI ainda não foi configurado para esta conta.</p>
                    )}
                  </section>
                </div>
              ) : null}

              {!loading && !config ? (
                <p className="text-muted mb-0">Nenhuma configuração disponível para este usuário.</p>
              ) : null}
            </div>
            <div className="modal-footer justify-content-between">
              <button type="button" className="btn btn-link text-decoration-none" onClick={onClose} disabled={resetting}>
                Fechar
              </button>
              <button type="button" className="btn btn-outline-danger" onClick={onReset} disabled={resetting || loading}>
                {resetting ? 'Resetando…' : 'Resetar painel XUI'}
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}
