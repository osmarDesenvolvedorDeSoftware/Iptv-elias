import { PropsWithChildren, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';

import { getLogDetail } from '../data/services/logService';

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

  useEffect(() => {
    setMountNode(document.body);
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
        console.error(error);
        if (!isMounted) {
          return;
        }
        setState({ loading: false, error: 'Não foi possível carregar o conteúdo detalhado do log.', content: '' });
      });

    return () => {
      isMounted = false;
    };
  }, [logId]);

  useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }

    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, [onClose]);

  const modalContent = useMemo(() => {
    if (state.loading) {
      return (
        <div className="d-flex align-items-center gap-2">
          <span className="spinner-border spinner-border-sm" aria-hidden="true" />
          <span>Carregando log…</span>
        </div>
      );
    }

    if (state.error) {
      return <div className="alert alert-danger mb-0">{state.error}</div>;
    }

    return (
      <pre className="mb-0 p-3 rounded border" style={{ maxHeight: '24rem', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
        {state.content}
      </pre>
    );
  }, [state.content, state.error, state.loading]);

  if (!mountNode) {
    return null;
  }

  return createPortal(
    <>
      <Backdrop>
        <div className="modal-dialog modal-lg modal-dialog-centered" role="dialog" aria-modal="true">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Log #{logId}</h5>
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onClose}>
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
