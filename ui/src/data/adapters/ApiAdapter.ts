import { API_BASE_URL } from '../../config';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiError {
  message: string;
  code?: string;
  details?: unknown;
  status?: number;
}

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  skipAuth?: boolean;
  retryCount?: number;
}

interface AuthHandlers {
  getAccessToken?: () => string | null;
  getTenantId?: () => string | null;
  refresh?: () => Promise<boolean>;
  onAuthFailure?: () => void;
}

const isDevelopment = Boolean(import.meta.env.DEV);

export const isMockEnabled =
  String(import.meta.env.VITE_USE_MOCK ?? 'false').toLowerCase() === 'true';

let authHandlers: AuthHandlers | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function configureAuthHandlers(handlers: AuthHandlers | null) {
  authHandlers = handlers;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const url = buildUrl(path);
  const headers = new Headers(options.headers);

  if (!options.skipAuth) {
    const token = authHandlers?.getAccessToken?.();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const tenantId = authHandlers?.getTenantId?.();
    if (tenantId) {
      headers.set('X-Tenant-ID', tenantId);
    }
  }

  let body: BodyInit | undefined;
  if (options.body instanceof FormData || options.body instanceof Blob) {
    body = options.body;
  } else if (options.body !== undefined && options.body !== null) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.body);
  }

  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.info('[ApiAdapter] request', { method, url, body });
  }

  let response: Response;

  try {
    response = await fetch(url, {
      method,
      headers,
      body,
      signal: options.signal,
    });
  } catch (error) {
    if (isDevelopment) {
      // eslint-disable-next-line no-console
      console.error('[ApiAdapter] network error', error);
    }

    throw normalizeNetworkError(error);
  }

  if (isDevelopment) {
    // eslint-disable-next-line no-console
    console.info('[ApiAdapter] response', { status: response.status, url });
  }

  if (response.status === 401 && !options.skipAuth) {
    const retried = options.retryCount ?? 0;

    if (retried === 0 && authHandlers?.refresh) {
      const refreshed = await attemptRefresh();

      if (refreshed) {
        return request<T>(path, { ...options, retryCount: retried + 1 });
      }
    }

    authHandlers?.onAuthFailure?.();

    throw <ApiError>{
      message: 'Sessão expirada. Faça login novamente.',
      code: 'unauthorized',
      status: 401,
    };
  }

  if (!response.ok) {
    throw await normalizeError(response);
  }

  return (await parseResponse<T>(response)) as T;
}

export function get<T>(path: string, options: RequestOptions = {}) {
  return request<T>(path, { ...options, method: 'GET' });
}

export function post<T>(path: string, body?: unknown, options: RequestOptions = {}) {
  return request<T>(path, { ...options, method: 'POST', body });
}

export function put<T>(path: string, body?: unknown, options: RequestOptions = {}) {
  return request<T>(path, { ...options, method: 'PUT', body });
}

export function patch<T>(path: string, body?: unknown, options: RequestOptions = {}) {
  return request<T>(path, { ...options, method: 'PATCH', body });
}

export function deleteRequest<T = void>(path: string, options: RequestOptions = {}) {
  return request<T>(path, { ...options, method: 'DELETE' });
}

function buildUrl(path: string): string {
  if (/^https?:/i.test(path)) {
    return path;
  }

  const baseUrl = API_BASE_URL;

  if (!baseUrl) {
    throw new Error('VITE_API_BASE_URL não configurada.');
  }

  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

async function parseResponse<T>(response: Response): Promise<T | undefined> {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}

async function normalizeError(response: Response): Promise<ApiError> {
  const contentType = response.headers.get('content-type') ?? '';
  let payload: unknown;

  try {
    if (contentType.includes('application/json')) {
      payload = await response.json();
    } else {
      payload = await response.text();
    }
  } catch (error) {
    if (isDevelopment) {
      // eslint-disable-next-line no-console
      console.error('[ApiAdapter] error parsing response', error);
    }
  }

  const asRecord = typeof payload === 'object' && payload !== null ? (payload as Record<string, unknown>) : null;

  const message =
    (typeof payload === 'string' && payload) ||
    (asRecord?.message as string | undefined) ||
    (asRecord?.error as string | undefined) ||
    'Falha ao processar resposta da API.';

  const code = (asRecord?.code as string | undefined) ?? (asRecord?.error as string | undefined);
  const details = asRecord?.details ?? (asRecord && Object.keys(asRecord).length > 0 ? asRecord : undefined);

  return {
    message,
    code,
    details,
    status: response.status,
  };
}

function normalizeNetworkError(error: unknown): ApiError {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return { message: 'Requisição cancelada.', code: 'aborted' };
  }

  if (error instanceof Error) {
    return {
      message: 'Não foi possível conectar ao serviço remoto.',
      details: { message: error.message },
    };
  }

  return { message: 'Falha desconhecida ao comunicar com a API.' };
}

async function attemptRefresh(): Promise<boolean> {
  if (!authHandlers?.refresh) {
    return false;
  }

  if (!refreshPromise) {
    refreshPromise = authHandlers
      .refresh()
      .catch((error) => {
        if (isDevelopment) {
          // eslint-disable-next-line no-console
          console.error('[ApiAdapter] refresh error', error);
        }
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}
