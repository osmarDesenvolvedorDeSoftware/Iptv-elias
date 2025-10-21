import { motion } from 'framer-motion';
import { ReactNode } from 'react';

interface ChartCardProps {
  title: string;
  description?: string;
  tooltip?: string;
  action?: ReactNode;
  footer?: ReactNode;
  isLoading?: boolean;
  children: ReactNode;
}

export function ChartCard({ title, description, tooltip, action, footer, isLoading, children }: ChartCardProps) {
  return (
    <motion.section
      className="dashboard-card"
      title={tooltip}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
    >
      <header className="dashboard-card__header">
        <div>
          <h3 className="dashboard-card__title">{title}</h3>
          {description ? <p className="dashboard-card__subtitle">{description}</p> : null}
        </div>
        {action ? <div className="dashboard-card__action">{action}</div> : null}
      </header>

      <div className={`dashboard-card__body${isLoading ? ' dashboard-card__body--loading' : ''}`}>
        {isLoading ? <div className="skeleton skeleton--chart" aria-hidden="true" /> : children}
      </div>

      {footer ? <footer className="dashboard-card__footer">{footer}</footer> : null}
    </motion.section>
  );
}
