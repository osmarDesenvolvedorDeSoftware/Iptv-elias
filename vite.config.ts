import { defineConfig, loadEnv, splitVendorChunkPlugin } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

const rootDir = resolve(__dirname, 'ui');

function resolveApiBaseUrl(mode: string): string {
  const projectEnv = loadEnv(mode, process.cwd(), '');
  const uiEnv = rootDir === process.cwd() ? projectEnv : loadEnv(mode, rootDir, '');
  const env = { ...projectEnv, ...uiEnv } as Record<string, string | undefined>;

  const configured = env.VITE_API_BASE_URL || process.env.VITE_API_BASE_URL || '';
  const fallback = mode === 'development' ? 'http://localhost:5000' : '';
  const finalValue = (configured || fallback).trim();
  const sanitized = finalValue.endsWith('/') ? finalValue.replace(/\/+$/, '') : finalValue;

  if (!configured) {
    if (fallback) {
      console.warn(
        `[vite] VITE_API_BASE_URL não encontrado nas variáveis de ambiente. Usando valor padrão: ${fallback}`,
      );
    } else {
      console.warn('[vite] VITE_API_BASE_URL não encontrado nas variáveis de ambiente.');
    }
  }

  process.env.VITE_API_BASE_URL = sanitized;

  console.info(
    `[vite] API base URL carregada (${mode}): ${sanitized || 'não definida (requer configuração)'}`,
  );

  return sanitized;
}

export default defineConfig(({ mode }) => {
  resolveApiBaseUrl(mode);

  return {
    root: rootDir,
    base: './',
    envDir: rootDir,
    plugins: [react(), splitVendorChunkPlugin()],
    resolve: {
      alias: {
        '@': resolve(rootDir, 'src'),
      },
    },
    build: {
      outDir: resolve(__dirname, 'dist'),
      emptyOutDir: true,
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('react-router')) {
                return 'vendor-react-router';
              }

              if (id.includes('react-dom') || id.includes('react')) {
                return 'vendor-react';
              }

              return 'vendor';
            }
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
    },
  };
});
