import { ConfigStatus } from '../../data/types';

export interface ConfigStatusCardProps {
  database: {
    host: string;
    port: number | null;
    name: string;
  };
  status: ConfigStatus;
  message?: string | null;
  testedAt?: string | null;
  testing?: boolean;
  tmdbConfigured: boolean;
  xtreamConfigured: boolean;
  useXtreamApi: boolean;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return 'Nunca testado';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Data desconhecida';
  }

  return date.toLocaleString('pt-BR');
}

function resolveBadgeVariant(status: ConfigStatus): string {
  if (status === 'success') return 'bg-success';
  if (status === 'error') return 'bg-danger';
  return 'bg-secondary';
}

function resolveStatusLabel(status: ConfigStatus, testing?: boolean): string {
  if (testing) {
    return 'Testando conexão…';
  }
  if (status === 'success') return 'Conexão verificada';
  if (status === 'error') return 'Falha na conexão';
  return 'Teste pendente';
}

export function ConfigStatusCard({
  database,
  status,
  message,
  testedAt,
  testing,
  tmdbConfigured,
  xtreamConfigured,
  useXtreamApi,
}: ConfigStatusCardProps) {
  const badgeClass = resolveBadgeVariant(status);
  const statusLabel = resolveStatusLabel(status, testing);

  return (
    <div className="card shadow-sm">
      <div className="card-header d-flex justify-content-between align-items-center">
        <span className="fw-semibold">Estado das Configurações</span>
        <span className={`badge ${badgeClass}`}>{statusLabel}</span>
      </div>

      <div className="card-body d-flex flex-column gap-3">
        <section>
          <h6 className="text-uppercase text-muted small fw-semibold mb-2">Banco de Dados</h6>
          <p className="mb-1">
            <span className="fw-semibold">Host:</span> {database.host || 'Não configurado'}
          </p>
          <p className="mb-1">
            <span className="fw-semibold">Porta:</span> {database.port ?? '—'}
          </p>
          <p className="mb-0">
            <span className="fw-semibold">Schema:</span> {database.name || '—'}
          </p>
        </section>

        <section>
          <h6 className="text-uppercase text-muted small fw-semibold mb-2">Diagnóstico</h6>
          <p className="mb-1">
            <span className="fw-semibold">Último teste:</span> {formatDate(testedAt)}
          </p>
          <p className="mb-0 text-muted" role="status" style={{ whiteSpace: 'pre-line' }}>
            {message || 'Nenhum teste executado até o momento.'}
          </p>
        </section>

        <section className="d-flex flex-column flex-md-row gap-3">
          <div className="flex-fill p-3 border rounded-3">
            <h6 className="text-uppercase text-muted small fw-semibold mb-2">TMDb</h6>
            <p className="mb-0">
              {tmdbConfigured ? (
                <span className="badge bg-success-subtle text-success fw-semibold">Chave configurada</span>
              ) : (
                <span className="badge bg-warning-subtle text-warning fw-semibold">Chave pendente</span>
              )}
            </p>
          </div>

          <div className="flex-fill p-3 border rounded-3">
            <h6 className="text-uppercase text-muted small fw-semibold mb-2">Xtream API</h6>
            <p className="mb-2">
              {useXtreamApi ? (
                <span className="badge bg-primary-subtle text-primary fw-semibold">API habilitada</span>
              ) : (
                <span className="badge bg-secondary-subtle text-secondary fw-semibold">API desabilitada</span>
              )}
            </p>
            <p className="mb-0 text-muted small">
              {xtreamConfigured ? 'Credenciais informadas.' : 'Informe usuário e senha para habilitar importação via API.'}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
