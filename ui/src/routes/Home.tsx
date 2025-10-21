import { Navigate } from 'react-router-dom';

import { useAuth } from '../providers/AuthProvider';

export default function Home() {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="d-flex align-items-center justify-content-center py-5" role="status" aria-live="polite">
        <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />
        <span>Carregando…</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={user.role === 'admin' ? '/admin/dashboard' : '/dashboard'} replace />;
}
