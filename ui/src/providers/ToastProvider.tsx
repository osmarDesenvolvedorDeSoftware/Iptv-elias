import {
  PropsWithChildren,
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

export type ToastVariant = 'success' | 'info' | 'error';

export interface ToastMessage {
  id: number;
  message: ReactNode;
  variant: ToastVariant;
}

interface ToastContextValue {
  toasts: ToastMessage[];
  push: (message: ReactNode, variant?: ToastVariant, options?: { duration?: number }) => void;
  remove: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);
let toastCounter = 0;
const TOAST_TIMEOUT_MS = 5000;

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (message: ReactNode, variant: ToastVariant = 'info', options: { duration?: number } = {}) => {
      toastCounter += 1;
      const id = toastCounter;

      setToasts((current) => [...current, { id, message, variant }]);

      const duration = typeof options.duration === 'number' && options.duration > 0 ? options.duration : TOAST_TIMEOUT_MS;

      window.setTimeout(() => {
        remove(id);
      }, duration);
    },
    [remove],
  );

  const value = useMemo(
    () => ({
      toasts,
      push,
      remove,
    }),
    [push, remove, toasts],
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error('useToast deve ser usado dentro de ToastProvider');
  }

  return context;
}
