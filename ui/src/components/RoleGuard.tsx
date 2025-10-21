import { PropsWithChildren } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../providers/AuthProvider';

type Role = 'admin' | 'user';

interface RoleGuardProps extends PropsWithChildren {
  roles?: Role[];
}

function defaultRedirect(role: Role): string {
  return role === 'admin' ? '/admin/dashboard' : '/dashboard';
}

export function RoleGuard({ roles, children }: RoleGuardProps) {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="d-flex align-items-center justify-content-center py-4" role="status" aria-live="polite">
        <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
        <span>Carregando…</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !roles.includes(user.role as Role)) {
    return <Navigate to={defaultRedirect(user.role as Role)} replace />;
  }

  return <>{children}</>;
}
