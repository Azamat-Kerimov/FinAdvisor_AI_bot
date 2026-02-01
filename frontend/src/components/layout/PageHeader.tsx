import { type ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Правый угол: иконка закрытия, меню. Масштабирование: вынести в slots (leftAction, rightAction) при усложнении. */
  rightAction?: ReactNode;
}

export function PageHeader({ title, subtitle, rightAction }: PageHeaderProps) {
  return (
    <header className="mb-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          {subtitle && (
            <p className="text-sm text-muted mb-0.5">{subtitle}</p>
          )}
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">{title}</h1>
        </div>
        {rightAction != null && <div className="flex-shrink-0">{rightAction}</div>}
      </div>
    </header>
  );
}
