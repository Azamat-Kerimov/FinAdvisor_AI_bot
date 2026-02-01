import { type ButtonHTMLAttributes, type ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  children: ReactNode;
  className?: string;
}

/** Кнопка: primary — основной CTA, secondary — вторичное действие, ghost — без фона. Масштабирование: добавить size (sm/md/lg) при необходимости. */
export function Button({ variant = 'primary', children, className = '', disabled, ...props }: ButtonProps) {
  const base = 'inline-flex items-center justify-center rounded-button font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-400 disabled:opacity-60 disabled:pointer-events-none';
  const variants = {
    primary: 'bg-slate-800 text-white hover:bg-slate-700 active:bg-slate-900 shadow-sm',
    secondary: 'bg-white border border-border text-slate-700 hover:bg-surface',
    ghost: 'text-slate-600 hover:bg-surface',
  };
  return (
    <button
      type="button"
      className={`${base} ${variants[variant]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
