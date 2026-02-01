#!/bin/bash
# Создаёт все недостающие файлы frontend/src (components, hooks, lib, types) на сервере.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p src/components/ui src/components/layout src/components/dashboard src/hooks src/lib src/types

# types/api.ts
cat > src/types/api.ts << 'EOF'
/** Ответ /api/stats — статистика за текущий месяц */
export interface Stats {
  total_income: number;
  total_expense: number;
  income_by_category: Record<string, number>;
  expense_by_category: Record<string, number>;
  reserve_recommended: number;
  insight: string;
}
EOF

# lib/api.ts
cat > src/lib/api.ts << 'EOF'
const API_BASE = import.meta.env.VITE_API_URL ?? '';

function getInitData(): string {
  if (typeof window !== 'undefined' && (window as unknown as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData) {
    return (window as unknown as { Telegram: { WebApp: { initData: string } } }).Telegram.WebApp.initData;
  }
  return '';
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(initData ? { 'init-data': initData } : {}),
    ...options.headers,
  };
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10_000);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      signal: options.signal ?? controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) {
      const text = await res.text();
      if (res.status === 401) throw new Error('Требуется авторизация. Откройте приложение через Telegram.');
      if (res.status === 403 && (text.includes('PREMIUM') || text.includes('premium'))) {
        throw new Error('Требуется подписка. Оформите подписку в боте.');
      }
      throw new Error(text || `Ошибка: ${res.status}`);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}
EOF

# hooks/useStats.ts
cat > src/hooks/useStats.ts << 'EOF'
import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/api';
import type { Stats } from '@/types/api';

export function useStats() {
  const [data, setData] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiRequest<Stats>('/api/stats', { signal: controller.signal })
      .then((res) => { if (!cancelled) setData(res); })
      .catch((e) => {
        if (!cancelled && e?.name !== 'AbortError') {
          setError(e instanceof Error ? e : new Error(String(e)));
          setData(null);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; controller.abort(); };
  }, []);

  return { data, loading, error };
}
EOF

# components/ui/Card.tsx
cat > src/components/ui/Card.tsx << 'EOF'
import { type ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = '' }: CardProps) {
  return (
    <div
      className={`rounded-card bg-white shadow-card border border-border/80 transition-shadow hover:shadow-card-hover ${className}`}
    >
      {children}
    </div>
  );
}
EOF

# components/ui/Button.tsx
cat > src/components/ui/Button.tsx << 'EOF'
import { type ButtonHTMLAttributes, type ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  children: ReactNode;
  className?: string;
}

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
EOF

# components/layout/PageHeader.tsx
cat > src/components/layout/PageHeader.tsx << 'EOF'
import { type ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  rightAction?: ReactNode;
}

export function PageHeader({ title, subtitle, rightAction }: PageHeaderProps) {
  return (
    <header className="mb-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          {subtitle && <p className="text-sm text-muted mb-0.5">{subtitle}</p>}
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">{title}</h1>
        </div>
        {rightAction != null && <div className="flex-shrink-0">{rightAction}</div>}
      </div>
    </header>
  );
}
EOF

# components/layout/BottomNav.tsx
cat > src/components/layout/BottomNav.tsx << 'EOF'
export type NavScreen = 'dashboard' | 'transactions' | 'capital' | 'consultation';

interface BottomNavProps {
  active: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

const items: { id: NavScreen; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Главная', icon: '🏠' },
  { id: 'transactions', label: 'Транзакции', icon: '💰' },
  { id: 'capital', label: 'Капитал', icon: '💼' },
  { id: 'consultation', label: 'ИИ', icon: '🤖' },
];

export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around bg-white border-t border-border py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-2px_12px_rgba(0,0,0,0.04)]">
      {items.map(({ id, label, icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onNavigate(id)}
          className={`flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-button text-[11px] font-medium transition-colors min-w-[64px] ${active === id ? 'text-slate-900' : 'text-muted hover:text-slate-600'}`}
        >
          <span className="text-[22px] leading-none">{icon}</span>
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
EOF

# components/layout/AppLayout.tsx
cat > src/components/layout/AppLayout.tsx << 'EOF'
import { type ReactNode } from 'react';
import { BottomNav, type NavScreen } from './BottomNav';

interface AppLayoutProps {
  children: ReactNode;
  activeScreen: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

export function AppLayout({ children, activeScreen, onNavigate }: AppLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 w-full max-w-[480px] mx-auto px-4 sm:px-6 pb-24">
        {children}
      </main>
      <BottomNav active={activeScreen} onNavigate={onNavigate} />
    </div>
  );
}
EOF

# components/dashboard/StatsCards.tsx
cat > src/components/dashboard/StatsCards.tsx << 'EOF'
import { Card } from '@/components/ui/Card';
import type { Stats } from '@/types/api';

function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(value));
}

interface StatsCardsProps {
  data: Stats;
  periodLabel?: string;
}

export function StatsCards({ data, periodLabel }: StatsCardsProps) {
  const income = data.total_income ?? 0;
  const expense = data.total_expense ?? 0;
  const savings = Math.max(0, income - expense);

  return (
    <div className="space-y-3">
      {periodLabel && <p className="text-sm text-muted mb-1">{periodLabel}</p>}
      <Card className="p-4 bg-income-light border-0">
        <div className="flex justify-between items-baseline">
          <span className="text-slate-700 font-medium">Доходы</span>
          <span className="text-lg font-bold text-slate-900">{formatMoney(income)} ₽</span>
        </div>
      </Card>
      <Card className="p-4 bg-expense-light border-0">
        <div className="flex justify-between items-baseline">
          <span className="text-slate-700 font-medium">Расходы</span>
          <span className="text-lg font-bold text-slate-900">{formatMoney(expense)} ₽</span>
        </div>
      </Card>
      <Card className="p-4 bg-savings-light border-0">
        <div className="flex justify-between items-baseline">
          <span className="text-slate-700 font-medium">Остаток</span>
          <span className="text-lg font-bold text-slate-900">{formatMoney(savings)} ₽</span>
        </div>
      </Card>
    </div>
  );
}
EOF

# components/dashboard/WelcomeCard.tsx
cat > src/components/dashboard/WelcomeCard.tsx << 'EOF'
import { Card } from '@/components/ui/Card';

export function WelcomeCard() {
  return (
    <Card className="p-6 text-center">
      <h2 className="text-lg font-semibold text-slate-900 mb-2">Добро пожаловать</h2>
      <p className="text-sm text-muted leading-relaxed">
        Добавьте операции или загрузите выписку из Сбера или Т‑Банка — статистика появится здесь.
      </p>
    </Card>
  );
}
EOF

# components/dashboard/InsightBlock.tsx
cat > src/components/dashboard/InsightBlock.tsx << 'EOF'
import { Card } from '@/components/ui/Card';
import type { Stats } from '@/types/api';

interface InsightBlockProps {
  data: Stats;
}

export function InsightBlock({ data }: InsightBlockProps) {
  const { insight, reserve_recommended } = data;
  const reserve = reserve_recommended ?? 0;
  const formatMoney = (v: number) => new Intl.NumberFormat('ru-RU').format(Math.round(v));

  if (!insight && reserve <= 0) return null;

  return (
    <Card className="p-4 mt-4">
      {insight && <p className="text-sm text-slate-600 leading-relaxed">{insight}</p>}
      {reserve > 0 && (
        <p className="text-sm text-muted mt-2">
          Рекомендуемый резервный фонд: {formatMoney(reserve)} ₽
        </p>
      )}
    </Card>
  );
}
EOF

# components/dashboard/DashboardScreen.tsx
cat > src/components/dashboard/DashboardScreen.tsx << 'EOF'
import { PageHeader } from '@/components/layout/PageHeader';
import { StatsCards } from './StatsCards';
import { WelcomeCard } from './WelcomeCard';
import { InsightBlock } from './InsightBlock';
import { useStats } from '@/hooks/useStats';

function currentMonthLabel(): string {
  const now = new Date();
  const month = now.toLocaleDateString('ru-RU', { month: 'long' });
  const day = now.getDate();
  return `1–${day} ${month}`;
}

export function DashboardScreen() {
  const { data, loading, error } = useStats();

  return (
    <>
      <PageHeader title="Денежный поток" subtitle={currentMonthLabel()} />
      {loading && (
        <div className="flex flex-col items-center justify-center py-12 text-muted">
          <div className="w-10 h-10 border-2 border-border border-t-slate-500 rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      )}
      {!loading && error && <WelcomeCard />}
      {!loading && data && (
        <>
          <StatsCards data={data} periodLabel={currentMonthLabel()} />
          <InsightBlock data={data} />
        </>
      )}
    </>
  );
}
EOF

echo "Created all frontend/src files. Run: cd $ROOT && npm run dev"