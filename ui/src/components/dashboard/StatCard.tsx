import { motion } from 'framer-motion';
import type { LucideIcon } from 'lucide-react';
import { Fragment, ReactNode } from 'react';

export type StatTone = 'primary' | 'success' | 'danger' | 'info' | 'warning';

export interface StatChip {
  label: string;
  value: string;
  tone?: StatTone;
}

interface StatCardProps {
  label: string;
  value: string | number;
  description?: string;
  icon: LucideIcon;
  accent?: StatTone;
  tooltip?: string;
  chips?: StatChip[];
  footer?: ReactNode;
  isLoading?: boolean;
  onClick?: () => void;
}

const accentClassMap: Record<StatTone, string> = {
  primary: 'dashboard-stat-card__icon--primary',
  success: 'dashboard-stat-card__icon--success',
  danger: 'dashboard-stat-card__icon--danger',
  info: 'dashboard-stat-card__icon--info',
  warning: 'dashboard-stat-card__icon--warning',
};

export function StatCard({
  label,
  value,
  description,
  icon: Icon,
  accent = 'primary',
  tooltip,
  chips,
  footer,
  isLoading,
  onClick,
}: StatCardProps) {
  const interactive = typeof onClick === 'function';
  const iconClass = accentClassMap[accent];

  return (
    <motion.div
      className={`dashboard-stat-card${interactive ? ' dashboard-stat-card--interactive' : ''}`}
      whileHover={{ y: -4 }}
      whileTap={interactive ? { scale: 0.98 } : undefined}
      onClick={onClick}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      title={tooltip}
    >
      <div className={`dashboard-stat-card__icon ${iconClass}`}>
        <Icon size={24} strokeWidth={1.75} />
      </div>

      <div className="dashboard-stat-card__content">
        <span className="dashboard-stat-card__label">{label}</span>
        <div className="dashboard-stat-card__value" aria-live="polite">
          {isLoading ? <span className="skeleton skeleton--text" /> : value}
        </div>
        {description ? <p className="dashboard-stat-card__description">{description}</p> : null}

        {chips && chips.length > 0 ? (
          <div className="dashboard-stat-card__chips">
            {chips.map((chip, index) => (
              <Fragment key={`${chip.label}-${index}`}>
                <span className={`dashboard-chip dashboard-chip--${chip.tone ?? 'info'}`} title={chip.label}>
                  <span className="dashboard-chip__label">{chip.label}</span>
                  <span className="dashboard-chip__value">{chip.value}</span>
                </span>
              </Fragment>
            ))}
          </div>
        ) : null}
      </div>

      {footer ? <div className="dashboard-stat-card__footer">{footer}</div> : null}
    </motion.div>
  );
}
