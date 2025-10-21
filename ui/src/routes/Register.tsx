import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { register as registerService } from '../data/services/authService';
import { useAuth } from '../providers/AuthProvider';

export default function Register() {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    if (password !== confirmPassword) {
      setError('As senhas não conferem.');
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      const response = await registerService({ name: name.trim(), email: email.trim(), password });
      setSession(response);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError?.message ?? 'Não foi possível concluir o cadastro.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="login-form" onSubmit={handleSubmit}>
      <div className="form-group mb-3">
        <label className="form-control-label" htmlFor="name">
          Nome completo
        </label>
        <input
          id="name"
          name="name"
          type="text"
          autoComplete="name"
          placeholder="Nome do responsável"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="form-control"
          required
        />
      </div>

      <div className="form-group mb-3">
        <label className="form-control-label" htmlFor="email">
          E-mail
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="usuario@exemplo.com"
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
          autoComplete="new-password"
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="form-control"
          required
          minLength={6}
        />
      </div>

      <div className="form-group mb-3">
        <label className="form-control-label" htmlFor="confirmPassword">
          Confirmar senha
        </label>
        <input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          placeholder="Repita a senha"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          className="form-control"
          required
          minLength={6}
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
            Criando conta…
          </span>
        ) : (
          'Criar conta'
        )}
      </button>

      <p className="text-muted text-center mt-3 mb-0">
        Já possui uma conta? <Link to="/login">Faça login</Link>.
      </p>
    </form>
  );
}
