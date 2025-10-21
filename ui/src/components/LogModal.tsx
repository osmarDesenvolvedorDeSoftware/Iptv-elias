import { PropsWithChildren, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { getLogDetail } from '../data/services/importService';

interface LogModalProps {
  logId: number;
  onClose: () => void;
}

interface LogModalState {
  loading: boolean;
  error: string | null;
  content: string;
}

const initialState: LogModalState = {
  loading: true,
  error: null,
  content: '',
};

function Backdrop({ children }: PropsWithChildren) {
  return (
    <div role="presentation" className="modal fade show" style={{ display: 'block' }}>
      {children}
    </div>
  );
}

export function LogModal({ logId, onClose }: LogModalProps) {
  const [state, setState] = useState<LogModalState>(initialState);
  const [mountNode, setMountNode] = useState<HTMLElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = `log-modal-title-${logId}`;
  const descriptionId = `log-modal-body-${logId}`;

  useEffect(() => {
    setMountNode(document.body);
  }, []);

  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null;

    const timeout = window.setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 0);

    return () => {
      window.clearTimeout(timeout);
      previousFocusRef.current?.focus();
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    setState(initialState);

    getLogDetail(logId)
      .then((response) => {
        if (!isMounted) {
          return;
        }
        setState({ loading: false, error: null, content: response.content });
      })
      .catch((error) => {
        const apiError = error as ApiError;
        if (!isMounted) {
          return;
        }
        setState({
          loading: false,
          error: apiError?.message ?? 'Não foi possível carregar o conteúdo detalhado do log.',
          content: '',
        });
      });

    return () => {
      isMounted = false;
    };
  }, [logId]);

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key === 'Tab' && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, textarea, select, details,[tabindex]:not([tabindex="-1"])',
        );

        if (focusable.length === 0) {
          event.preventDefault();
          closeButtonRef.current?.focus();
          return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const activeElement = document.activeElement as HTMLElement | null;

        if (event.shiftKey) {
          if (!activeElement || activeElement === first) {
            event.preventDefault();
            last.focus();
          }
        } else if (activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }

    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, [onClose]);

  const modalContent = useMemo(() => {
    if (state.loading) {
      return (
        <div
          id={descriptionId}
          className="d-flex align-items-center gap-2"
          role="status"
          aria-live="polite"
        >
          <span className="spinner-border spinner-border-sm" aria-hidden="true" />
          <span>Carregando log…</span>
        </div>
      );
    }

    if (state.error) {
      return (
        <div id={descriptionId} className="alert alert-danger mb-0" role="alert" aria-live="assertive">
          {state.error}
        </div>
      );
    }

    return (
      <pre
        id={descriptionId}
        className="mb-0 p-3 rounded border"
        style={{ maxHeight: '24rem', overflowY: 'auto', whiteSpace: 'pre-wrap' }}
        aria-live="polite"
      >
        {state.content}
      </pre>
    );
  }, [descriptionId, state.content, state.error, state.loading]);

  if (!mountNode) {
    return null;
  }

  return createPortal(
    <>
      <Backdrop>
        <div
          className="modal-dialog modal-lg modal-dialog-centered"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
        >
          <div className="modal-content" ref={dialogRef}>
            <div className="modal-header">
              <h5 id={titleId} className="modal-title">
                Log #{logId}
              </h5>
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={onClose}
                ref={closeButtonRef}
                aria-label="Fechar modal de log"
              >
                Fechar
              </button>
            </div>
            <div className="modal-body">{modalContent}</div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      </Backdrop>
      <div className="modal-backdrop fade show" />
    </>,
    mountNode,
  );
}
