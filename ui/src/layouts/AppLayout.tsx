import { PropsWithChildren } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { useTheme } from '../providers/ThemeProvider';

const navigation = [
  { label: 'Dashboard', to: '/' },
  { label: 'Importação', to: '/importacao' },
  { label: 'Bouquets', to: '/bouquets' },
  { label: 'Relatórios', to: '/relatorios' },
  { label: 'Configurações', to: '/configuracoes' },
];

export function AppLayout({ children }: PropsWithChildren) {
  const { mode, toggle } = useTheme();

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
            <button type="button" className="app-shell__action">
              Perfil
            </button>
          </div>
        </header>

        <main className="app-shell__content">
          {children ?? <Outlet />}
        </main>
      </div>
    </div>
  );
}
