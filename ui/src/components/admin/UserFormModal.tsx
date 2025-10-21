import { FormEvent, useEffect, useId, useMemo, useState } from 'react';

import type { AdminUser } from '../../data/types';

interface UserFormModalProps {
  open: boolean;
  mode: 'create' | 'edit';
  user?: AdminUser | null;
  submitting?: boolean;
  onSubmit: (payload: {
    name: string;
    email: string;
    password?: string;
    isAdmin: boolean;
    isActive: boolean;
  }) => void;
  onClose: () => void;
}

interface FormState {
  name: string;
  email: string;
  password: string;
  isAdmin: boolean;
  isActive: boolean;
}

const initialState: FormState = {
  name: '',
  email: '',
  password: '',
  isAdmin: false,
  isActive: true,
};

export function UserFormModal({ open, mode, user, submitting = false, onSubmit, onClose }: UserFormModalProps) {
  const [form, setForm] = useState<FormState>(initialState);
  const [touched, setTouched] = useState(false);
  const modalId = useId();
  const titleId = `${modalId}-title`;

  useEffect(() => {
    if (!open) {
      setForm(initialState);
      setTouched(false);
      return;
    }

    if (mode === 'edit' && user) {
      setForm({
        name: user.name,
        email: user.email,
        password: '',
        isAdmin: user.role === 'admin',
        isActive: user.isActive,
      });
    } else {
      setForm(initialState);
    }
    setTouched(false);
  }, [open, mode, user]);

  const passwordRequired = mode === 'create';

  const isValid = useMemo(() => {
    const trimmedName = form.name.trim();
    const trimmedEmail = form.email.trim();
    if (!trimmedName || !trimmedEmail) {
      return false;
    }
    if (passwordRequired && form.password.trim().length < 6) {
      return false;
    }
    return true;
  }, [form.email, form.name, form.password, passwordRequired]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTouched(true);

    if (!isValid) {
      return;
    }

    const payload = {
      name: form.name.trim(),
      email: form.email.trim().toLowerCase(),
      password: form.password.trim() || undefined,
      isAdmin: form.isAdmin,
      isActive: form.isActive,
    };

    if (!passwordRequired && !payload.password) {
      delete payload.password;
    }

    onSubmit(payload);
  }

  if (!open) {
    return null;
  }

  return (
    <>
      <div className="modal fade show" style={{ display: 'block' }} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="modal-dialog modal-lg modal-dialog-centered">
          <div className="modal-content">
            <form onSubmit={handleSubmit}>
              <div className="modal-header">
                <h5 className="modal-title" id={titleId}>
                  {mode === 'create' ? 'Nova conta IPTV' : `Editar conta #${user?.id ?? ''}`}
                </h5>
                <button type="button" className="btn-close" onClick={onClose} aria-label="Fechar" />
              </div>
              <div className="modal-body">
                <div className="row g-3">
                  <div className="col-12 col-md-6">
                    <label htmlFor={`${modalId}-name`} className="form-label text-uppercase small text-muted">
                      Nome completo
                    </label>
                    <input
                      id={`${modalId}-name`}
                      type="text"
                      className="form-control"
                      value={form.name}
                      onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                      required
                    />
                  </div>
                  <div className="col-12 col-md-6">
                    <label htmlFor={`${modalId}-email`} className="form-label text-uppercase small text-muted">
                      Email
                    </label>
                    <input
                      id={`${modalId}-email`}
                      type="email"
                      className="form-control"
                      value={form.email}
                      onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                      required
                    />
                  </div>
                  <div className="col-12 col-md-6">
                    <label htmlFor={`${modalId}-password`} className="form-label text-uppercase small text-muted">
                      Senha {passwordRequired ? '' : '(opcional)'}
                    </label>
                    <input
                      id={`${modalId}-password`}
                      type="password"
                      className="form-control"
                      value={form.password}
                      onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                      placeholder={passwordRequired ? 'Mínimo 6 caracteres' : 'Preencha para redefinir'}
                      minLength={passwordRequired ? 6 : undefined}
                    />
                    {touched && passwordRequired && form.password.trim().length < 6 ? (
                      <div className="form-text text-danger">Informe uma senha com pelo menos 6 caracteres.</div>
                    ) : null}
                  </div>
                  <div className="col-12 col-md-3">
                    <div className="form-check mt-4">
                      <input
                        id={`${modalId}-is-admin`}
                        className="form-check-input"
                        type="checkbox"
                        checked={form.isAdmin}
                        onChange={(event) => setForm((current) => ({ ...current, isAdmin: event.target.checked }))}
                      />
                      <label htmlFor={`${modalId}-is-admin`} className="form-check-label">
                        Conceder privilégios de administrador
                      </label>
                    </div>
                  </div>
                  <div className="col-12 col-md-3">
                    <div className="form-check mt-4">
                      <input
                        id={`${modalId}-is-active`}
                        className="form-check-input"
                        type="checkbox"
                        checked={form.isActive}
                        onChange={(event) => setForm((current) => ({ ...current, isActive: event.target.checked }))}
                      />
                      <label htmlFor={`${modalId}-is-active`} className="form-check-label">
                        Conta ativa
                      </label>
                    </div>
                  </div>
                </div>
              </div>
              <div className="modal-footer justify-content-between">
                <button type="button" className="btn btn-link text-decoration-none" onClick={onClose} disabled={submitting}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting || !isValid}>
                  {submitting ? 'Salvando…' : 'Salvar alterações'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>
  );
}
