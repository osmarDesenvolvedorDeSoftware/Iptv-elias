import { FormEvent, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { login as loginService } from '../data/services/authService';
import { useAuth } from '../providers/AuthProvider';

export default function Login() {
  const navigate = useNavigate();
  const { setSession, isAuthenticated, isLoading, mockCredentials } = useAuth();
  const [email, setEmail] = useState(() => mockCredentials?.email ?? '');
  const [password, setPassword] = useState(() => mockCredentials?.password ?? '');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const emailInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/importacao', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  useEffect(() => {
    if (!isLoading) {
      emailInputRef.current?.focus();
    }
  }, [isLoading]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting || isLoading) {
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const response = await loginService({ email: email.trim(), password });
      setSession(response);
      navigate('/importacao');
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível realizar o login no momento.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="login-form" onSubmit={handleSubmit}>
      <div className="form-group mb-3">
        <label className="form-control-label" htmlFor="email">
          E-mail
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          placeholder={mockCredentials?.email ?? 'usuario@tenant.com'}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="form-control"
          required
          ref={emailInputRef}
        />
      </div>

      <div className="form-group mb-3">
        <label className="form-control-label" htmlFor="password">
          Senha
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder={mockCredentials?.password ?? '••••••••'}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="form-control"
          required
        />
      </div>

      {error ? (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      ) : null}

      <button type="submit" className="btn btn-primary w-100" disabled={isSubmitting || isLoading}>
        {isSubmitting ? (
          <span className="d-inline-flex align-items-center justify-content-center gap-2">
            <span className="spinner-border spinner-border-sm" aria-hidden="true" />
            Entrando…
          </span>
        ) : (
          'Entrar'
        )}
      </button>

      {mockCredentials ? (
        <p className="text-muted text-center mt-3 mb-0">
          Use <strong>{mockCredentials.email}</strong> com senha <strong>{mockCredentials.password}</strong> para autenticar no
          modo mock.
        </p>
      ) : null}
    </form>
  );
}
