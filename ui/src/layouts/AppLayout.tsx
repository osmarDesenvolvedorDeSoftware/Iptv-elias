import { PropsWithChildren, useMemo } from 'react';
import { NavLink, Navigate, Outlet } from 'react-router-dom';

import { useAuth } from '../providers/AuthProvider';
import { useTheme } from '../providers/ThemeProvider';

const adminNavigation = [
  { label: 'Dashboard', to: '/admin/dashboard' },
  { label: 'Importação', to: '/importacao' },
  { label: 'Bouquets', to: '/bouquets' },
  { label: 'Relatórios & Logs', to: '/logs' },
  { label: 'Configurações', to: '/configuracoes' },
  { label: 'Tenants', to: '/tenants' },
];

const userNavigation = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Logs', to: '/logs' },
];

function createInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
    .padEnd(2, '•');
}

export function AppLayout({ children }: PropsWithChildren) {
  const { mode, toggle } = useTheme();
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  const navigation = useMemo(() => {
    return user?.role === 'admin' ? adminNavigation : userNavigation;
  }, [user?.role]);

  if (!isLoading && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <div className="app-shell__brand">Painel IPTV</div>
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

            <div className="app-shell__profile" title={user?.tenantName ?? user?.tenantId ?? 'Tenant não definido'}>
              <span className="app-shell__avatar" aria-hidden="true">
                {createInitials(user?.name ?? 'Usuário')}
              </span>
              <div className="app-shell__profile-info">
                <span className="app-shell__profile-name">{user?.name ?? 'Usuário'}</span>
                <span className="app-shell__profile-tenant">{user?.tenantName ?? user?.tenantId ?? 'Sem tenant'}</span>
              </div>
            </div>

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
