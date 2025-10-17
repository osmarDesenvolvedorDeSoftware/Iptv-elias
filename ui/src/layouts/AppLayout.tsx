import { PropsWithChildren } from 'react';
import { NavLink, Navigate, Outlet } from 'react-router-dom';

import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';

const navigation = [
  { label: 'Dashboard', to: '/' },
  { label: 'Importação', to: '/importacao' },
  { label: 'Bouquets', to: '/bouquets' },
  { label: 'Relatórios & Logs', to: '/logs' },
  { label: 'Configurações', to: '/configuracoes' },
];

export function AppLayout({ children }: PropsWithChildren) {
  const { mode, toggle } = useTheme();
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  if (!isLoading && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <div className="app-shell__brand">IPTV Admin</div>
        <nav>
          <ul>
            {navigation.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to}>{item.label}</NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <div className="app-shell__main">
        <header className="app-shell__navbar">
          <span className="app-shell__title">Central IPTV</span>
          <div className="app-shell__actions">
            <button type="button" className="app-shell__action" onClick={toggle}>
              Tema: {mode === 'light' ? '🌞' : '🌙'}
            </button>
            <span className="app-shell__action">
              {user ? user.name : 'Usuário'}
            </span>
            <button type="button" className="app-shell__action" onClick={logout}>
              Sair
            </button>
          </div>
        </header>

        <main className="app-shell__content">
          {isLoading ? (
            <div className="d-flex align-items-center justify-content-center gap-2 py-5">
              <span className="spinner-border spinner-border-sm" aria-hidden="true" />
              <span>Verificando sessão…</span>
            </div>
          ) : (
            children ?? <Outlet />
          )}
        </main>
      </div>
    </div>
  );
}
