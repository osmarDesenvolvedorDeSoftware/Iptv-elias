const rawValue = (import.meta.env.VITE_API_BASE_URL ?? '').toString().trim();
const mode = import.meta.env.MODE ?? 'development';
const fallback = !rawValue && mode === 'development' ? 'http://localhost:5000' : '';
const normalizedValue = (rawValue || fallback).replace(/\/+$/, '');

export const API_BASE_URL = normalizedValue;

if (!rawValue && fallback) {
  // eslint-disable-next-line no-console
  console.warn(
    `[config] VITE_API_BASE_URL não encontrado. Usando valor padrão de desenvolvimento: ${fallback}`,
  );
}

if (API_BASE_URL) {
  // eslint-disable-next-line no-console
  console.info(`[config] API base URL carregada (${mode}): ${API_BASE_URL}`);
} else {
  // eslint-disable-next-line no-console
  console.warn('[config] API base URL não definida. Certifique-se de configurar VITE_API_BASE_URL.');
}
