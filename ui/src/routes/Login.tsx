import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { login as loginService } from '../data/services/authService';
import { useAuth } from '../providers/AuthProvider';

const MOCK_PASSWORD = 'admin123';
const MOCK_EMAIL = 'operador@tenant.com';

export default function Login() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const response = await loginService();
      const normalizedEmail = email.trim().toLowerCase();

      if (normalizedEmail !== response.user.email.toLowerCase() || password !== MOCK_PASSWORD) {
        setError('Credenciais incorretas. Utilize o usuário e senha mockados.');
        return;
      }

      setSession(response);
      navigate('/importacao');
    } catch (err) {
      setError('Não foi possível realizar o login no momento.');
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
          placeholder={MOCK_EMAIL}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="form-control"
          required
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
          placeholder="admin123"
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

      <button type="submit" className="btn btn-primary w-100" disabled={isSubmitting}>
        {isSubmitting ? (
          <span className="d-inline-flex align-items-center justify-content-center gap-2">
            <span className="spinner-border spinner-border-sm" aria-hidden="true" />
            Entrando…
          </span>
        ) : (
          'Entrar'
        )}
      </button>

      <p className="text-muted text-center mt-3 mb-0">
        Use <strong>{MOCK_EMAIL}</strong> com senha <strong>{MOCK_PASSWORD}</strong> para autenticar.
      </p>
    </form>
  );
}
