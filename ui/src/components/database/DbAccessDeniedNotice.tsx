import type { ReactNode } from 'react';

export interface DbAccessDeniedNoticeProps {
  message: string;
  hint?: string | null;
}

function extractMessageSegments(message: string): string[] {
  const normalized = message.trim();
  if (!normalized) {
    return [];
  }

  const lines = normalized
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const sentences: string[] = [];

  for (const line of lines.length > 0 ? lines : [normalized]) {
    const segments = line
      .split(/(?<=\.)\s+/)
      .map((segment) => segment.trim())
      .filter((segment) => segment.length > 0);

    if (segments.length > 0) {
      sentences.push(...segments);
    } else {
      sentences.push(line);
    }
  }

  return sentences;
}

export function DbAccessDeniedNotice({ message, hint }: DbAccessDeniedNoticeProps) {
  const segments = extractMessageSegments(message);

  const content: ReactNode[] =
    segments.length > 0
      ? segments.map((segment, index) => (
          <p key={`${index}-${segment}`} className="db-access-denied-notice__line">
            <span
              className={
                index === 0
                  ? 'db-access-denied-notice__icon'
                  : 'db-access-denied-notice__icon db-access-denied-notice__icon--spacer'
              }
              aria-hidden="true"
            >
              ❌
            </span>
            <span>{segment}</span>
          </p>
        ))
      : [
          <p key="fallback" className="db-access-denied-notice__line">
            <span className="db-access-denied-notice__icon" aria-hidden="true">
              ❌
            </span>
            <span>{message}</span>
          </p>,
        ];

  return (
    <div className="db-access-denied-notice">
      <div className="db-access-denied-notice__message" role="text">
        {content}
      </div>
      {hint ? (
        <pre className="db-access-denied-notice__hint" aria-label="Comando SQL sugerido">
          <code>{hint}</code>
        </pre>
      ) : null}
    </div>
  );
}
