import { type ReactNode, type MouseEventHandler } from 'react';

export interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLDivElement>;
}

/** Базовая карточка: фон, скругление, тень. Масштабирование: добавлять варианты (variant) при появлении новых типов блоков. */
export function Card({ children, className = '', onClick }: CardProps) {
  return (
    <div
      role={onClick ? 'button' : undefined}
      className={`rounded-card bg-white shadow-card border border-border/80 transition-shadow hover:shadow-card-hover ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
