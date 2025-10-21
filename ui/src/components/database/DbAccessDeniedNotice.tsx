import { getDbAccessDeniedFallbackMessage } from '../../utils/dbErrors';

export interface DbAccessDeniedNoticeProps {
  error: { message?: string | null; code?: string | null } | null | undefined;
  hint?: string | null;
}

export const DbAccessDeniedNotice = ({ error, hint }: DbAccessDeniedNoticeProps) => {
  const message =
    typeof error?.message === 'string' && error.message.trim().length > 0
      ? error.message.trim()
      : getDbAccessDeniedFallbackMessage();

  const normalizedHint =
    typeof hint === 'string' && hint.trim().length > 0 ? hint.trim() : null;

  return (
    <div className="db-error-toast">
      <strong>❌ {message}</strong>
      {normalizedHint ? <pre className="db-hint">{normalizedHint}</pre> : null}
    </div>
  );
};
