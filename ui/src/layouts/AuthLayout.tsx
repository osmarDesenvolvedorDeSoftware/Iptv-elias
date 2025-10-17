import { PropsWithChildren } from 'react';
import { Outlet } from 'react-router-dom';

import { useTheme } from '../providers/ThemeProvider';

export function AuthLayout({ children }: PropsWithChildren) {
  const { mode, toggle } = useTheme();

  return (
    <div className="auth-shell">
      <main className="auth-shell__content">
        <div className="auth-shell__card card shadow-sm p-4">
          <div className="d-flex justify-content-end mb-2">
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={toggle}>
              Tema: {mode === 'light' ? '🌞' : '🌙'}
            </button>
          </div>
          <h1 className="h4 text-center mb-4">Acessar painel IPTV</h1>
          {children ?? <Outlet />}
        </div>
      </main>
    </div>
  );
}
