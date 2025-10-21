import { useToast } from '../providers/ToastProvider';

const variantClassMap = {
  success: 'alert alert-success shadow',
  error: 'alert alert-danger shadow',
  info: 'alert alert-info shadow',
} as const;

export function ToastContainer() {
  const { toasts, remove } = useToast();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div
      className="toast-container position-fixed p-3"
      style={{ top: '1.5rem', right: '1.5rem', zIndex: 1080, minWidth: '18rem', position: 'fixed' }}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label="Notificações"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`${variantClassMap[toast.variant]} d-flex align-items-center justify-content-between gap-3 mb-2`}
          data-variant={toast.variant}
          role="alert"
        >
          <span className="me-3" style={{ whiteSpace: 'pre-line' }}>
            {toast.message}
          </span>
          <button
            type="button"
            className="btn btn-sm btn-link text-reset"
            aria-label="Fechar notificação"
            onClick={() => remove(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
