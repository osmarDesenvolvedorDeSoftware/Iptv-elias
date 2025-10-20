import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react';

import type { TenantSummary } from '../data/types';
import { createTenant, listTenants } from '../data/services/tenantService';
import { useToast } from '../providers/ToastProvider';

interface TenantForm {
  id: string;
  name: string;
  xuiDbUri: string;
  xtreamBaseUrl: string;
  xtreamUsername: string;
  xtreamPassword: string;
  tmdbKey: string;
  ignorePrefixes: string;
  ignoreCategories: string;
}

const initialForm: TenantForm = {
  id: '',
  name: '',
  xuiDbUri: '',
  xtreamBaseUrl: '',
  xtreamUsername: '',
  xtreamPassword: '',
  tmdbKey: '',
  ignorePrefixes: '',
  ignoreCategories: '',
};

function sanitizeList(value: string): string[] {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
}

function sanitizeCategoryList(value: string): Array<string | number> {
  return sanitizeList(value).map((entry) => {
    const numeric = Number(entry);
    return Number.isFinite(numeric) ? numeric : entry;
  });
}

export default function Tenants() {
  const { push } = useToast();
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<TenantForm>(initialForm);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadTenants() {
      setLoading(true);
      setError(null);

      try {
        const response = await listTenants();
        if (!cancelled) {
          setTenants(response);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError((loadError as { message?: string })?.message ?? 'Não foi possível carregar os tenants.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadTenants();

    return () => {
      cancelled = true;
    };
  }, []);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  const isValid = useMemo(() => {
    return form.id.trim().length >= 3 && form.name.trim().length >= 3;
  }, [form.id, form.name]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isValid) {
      push('Informe ao menos o ID e o nome do tenant.', 'error');
      return;
    }

    const trimmedId = form.id.trim().toLowerCase();
    const trimmedName = form.name.trim();

    const integrationPayload = {
      xuiDbUri: form.xuiDbUri.trim() || undefined,
      xtreamBaseUrl: form.xtreamBaseUrl.trim() || undefined,
      xtreamUsername: form.xtreamUsername.trim() || undefined,
      xtreamPassword: form.xtreamPassword.trim() || undefined,
      tmdbKey: form.tmdbKey.trim() || undefined,
      ignorePrefixes: sanitizeList(form.ignorePrefixes),
      ignoreCategories: sanitizeCategoryList(form.ignoreCategories),
    };

    const hasIntegration = Object.values({
      xuiDbUri: integrationPayload.xuiDbUri,
      xtreamBaseUrl: integrationPayload.xtreamBaseUrl,
      xtreamUsername: integrationPayload.xtreamUsername,
      xtreamPassword: integrationPayload.xtreamPassword,
      tmdbKey: integrationPayload.tmdbKey,
    }).some((value) => Boolean(value)) || integrationPayload.ignorePrefixes.length > 0 || integrationPayload.ignoreCategories.length > 0;

    setSubmitting(true);

    try {
      const response = await createTenant({
        id: trimmedId,
        name: trimmedName,
        integration: hasIntegration ? integrationPayload : undefined,
      });

      setTenants((current) => [...current, response.tenant]);
      setForm(initialForm);
      push('Tenant criado com sucesso.', 'success');
    } catch (submitError) {
      const apiError = submitError as { message?: string };
      push(apiError?.message ?? 'Não foi possível criar o tenant.', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="container-fluid py-4">
      <header className="d-flex flex-column align-items-center mb-4 text-center">
        <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
          Dashboard / Tenants
        </nav>
        <h1 className="display-6 mb-0">Gestão de Tenants</h1>
      </header>

      <div className="row g-4">
        <div className="col-12 col-lg-5">
          <div className="card shadow-sm">
            <div className="card-header">
              <h2 className="h5 mb-0">Adicionar Tenant</h2>
            </div>
            <form onSubmit={handleSubmit} className="card-body">{
              error ? (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              ) : null
            }
              <div className="mb-3">
                <label htmlFor="tenant-id" className="form-label text-uppercase small text-muted">
                  Tenant ID
                </label>
                <input
                  id="tenant-id"
                  name="id"
                  type="text"
                  className="form-control"
                  value={form.id}
                  onChange={handleChange}
                  placeholder="ex.: tenant-filial"
                  required
                />
                <div className="form-text">Use letras minúsculas, números, hífen ou underline.</div>
              </div>
              <div className="mb-3">
                <label htmlFor="tenant-name" className="form-label text-uppercase small text-muted">
                  Nome
                </label>
                <input
                  id="tenant-name"
                  name="name"
                  type="text"
                  className="form-control"
                  value={form.name}
                  onChange={handleChange}
                  required
                />
              </div>
              <div className="mb-3">
                <label htmlFor="tenant-xui-uri" className="form-label text-uppercase small text-muted">
                  URI do banco XUI
                </label>
                <input
                  id="tenant-xui-uri"
                  name="xuiDbUri"
                  type="text"
                  className="form-control"
                  value={form.xuiDbUri}
                  onChange={handleChange}
                  placeholder="mysql+pymysql://user:senha@host:3306/xui"
                />
              </div>
              <div className="mb-3">
                <label htmlFor="tenant-xtream-base" className="form-label text-uppercase small text-muted">
                  Xtream Base URL
                </label>
                <input
                  id="tenant-xtream-base"
                  name="xtreamBaseUrl"
                  type="text"
                  className="form-control"
                  value={form.xtreamBaseUrl}
                  onChange={handleChange}
                  placeholder="https://painel.provedor.com"
                />
              </div>
              <div className="row g-3">
                <div className="col-12 col-md-6">
                  <label htmlFor="tenant-xtream-user" className="form-label text-uppercase small text-muted">
                    Xtream Usuário
                  </label>
                  <input
                    id="tenant-xtream-user"
                    name="xtreamUsername"
                    type="text"
                    className="form-control"
                    value={form.xtreamUsername}
                    onChange={handleChange}
                  />
                </div>
                <div className="col-12 col-md-6">
                  <label htmlFor="tenant-xtream-pass" className="form-label text-uppercase small text-muted">
                    Xtream Senha
                  </label>
                  <input
                    id="tenant-xtream-pass"
                    name="xtreamPassword"
                    type="password"
                    className="form-control"
                    value={form.xtreamPassword}
                    onChange={handleChange}
                  />
                </div>
              </div>
              <div className="mt-3">
                <label htmlFor="tenant-tmdb-key" className="form-label text-uppercase small text-muted">
                  TMDb Key
                </label>
                <input
                  id="tenant-tmdb-key"
                  name="tmdbKey"
                  type="text"
                  className="form-control"
                  value={form.tmdbKey}
                  onChange={handleChange}
                  placeholder="Opcional, pode ser configurado depois"
                />
              </div>
              <div className="row g-3 mt-1">
                <div className="col-12 col-md-6">
                  <label htmlFor="tenant-ignore-prefixes" className="form-label text-uppercase small text-muted">
                    Prefixos ignorados
                  </label>
                  <input
                    id="tenant-ignore-prefixes"
                    name="ignorePrefixes"
                    type="text"
                    className="form-control"
                    value={form.ignorePrefixes}
                    onChange={handleChange}
                    placeholder="ex.: [TESTE, DEMO]"
                  />
                </div>
                <div className="col-12 col-md-6">
                  <label htmlFor="tenant-ignore-categories" className="form-label text-uppercase small text-muted">
                    Categorias ignoradas (IDs)
                  </label>
                  <input
                    id="tenant-ignore-categories"
                    name="ignoreCategories"
                    type="text"
                    className="form-control"
                    value={form.ignoreCategories}
                    onChange={handleChange}
                    placeholder="Separadas por vírgula"
                  />
                </div>
              </div>
              <div className="d-flex justify-content-end mt-4">
                <button type="submit" className="btn btn-primary" disabled={!isValid || submitting}>
                  {submitting ? (
                    <span className="d-inline-flex align-items-center gap-2">
                      <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                      Salvando…
                    </span>
                  ) : (
                    'Adicionar tenant'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
        <div className="col-12 col-lg-7">
          <div className="card shadow-sm">
            <div className="card-header d-flex align-items-center justify-content-between">
              <h2 className="h5 mb-0">Tenants cadastrados</h2>
              {loading ? (
                <span className="text-muted small">Carregando…</span>
              ) : (
                <span className="badge bg-secondary" aria-label="Total de tenants">
                  {tenants.length}
                </span>
              )}
            </div>
            <div className="card-body p-0">
              {loading ? (
                <div className="p-4 text-center text-muted">Carregando tenants…</div>
              ) : tenants.length === 0 ? (
                <div className="p-4 text-center text-muted">Nenhum tenant cadastrado até o momento.</div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-hover align-middle mb-0">
                    <thead className="table-light text-uppercase small text-muted">
                      <tr>
                        <th scope="col">Tenant</th>
                        <th scope="col">Nome</th>
                        <th scope="col">Criado em</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tenants.map((tenant) => (
                        <tr key={tenant.id}>
                          <td className="fw-semibold">{tenant.id}</td>
                          <td>{tenant.name}</td>
                          <td>{tenant.createdAt ? new Date(tenant.createdAt).toLocaleString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
