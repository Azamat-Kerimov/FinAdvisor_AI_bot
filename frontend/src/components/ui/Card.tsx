import { type ReactNode, type MouseEventHandler } from 'react';

export interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLDivElement>;
}

/** Карточка в стиле Telegram: лёгкое скругление, мягкая тень, светлый фон. */
export function Card({ children, className = '', onClick }: CardProps) {
  return (
    <div
      role={onClick ? 'button' : undefined}
      className={`rounded-card bg-white dark:bg-slate-800 shadow-card border border-slate-200/80 dark:border-slate-600/80 transition-shadow hover:shadow-card-hover ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
