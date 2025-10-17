import { PropsWithChildren } from 'react';
import { Outlet } from 'react-router-dom';

export function AuthLayout({ children }: PropsWithChildren) {
  return (
    <div className="auth-shell">
      <main className="auth-shell__content">
        <div className="auth-shell__card">
          <h1 className="auth-shell__title">Acessar painel IPTV</h1>
          {children ?? <Outlet />}
        </div>
      </main>
    </div>
  );
}
