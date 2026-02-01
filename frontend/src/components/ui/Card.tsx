import { type ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
}

/** Базовая карточка: фон, скругление, тень. Масштабирование: добавлять варианты (variant) при появлении новых типов блоков. */
export function Card({ children, className = '' }: CardProps) {
  return (
    <div
      className={`rounded-card bg-white shadow-card border border-border/80 transition-shadow hover:shadow-card-hover ${className}`}
    >
      {children}
    </div>
  );
}
