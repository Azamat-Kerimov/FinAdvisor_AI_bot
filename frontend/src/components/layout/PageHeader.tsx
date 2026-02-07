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
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <div />
        <div className="min-w-0 text-center">
          {subtitle && (
            <p className="text-sm text-muted mb-0.5">{subtitle}</p>
          )}
          <h1 className="text-xl font-bold text-slate-900 tracking-tight truncate">{title}</h1>
        </div>
        <div className="flex justify-end">{rightAction ?? <span />}</div>
      </div>
    </header>
  );
}
