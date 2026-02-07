import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/api';

interface GoalInsight {
  goals: Array<{
    id: number;
    title: string;
    target: number;
    current: number;
    remaining: number;
    months_to_goal: number | null;
  }>;
  monthly_savings: number;
}

interface GoalsSummaryProps {
  variant?: 'light' | 'dark';
}

export function GoalsSummary({ variant = 'light' }: GoalsSummaryProps) {
  const [data, setData] = useState<GoalInsight | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiRequest<GoalInsight>('/api/goals/insight')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading || !data || data.goals.length === 0) return null;

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }

  const isDark = variant === 'dark';

  return (
    <div
      className={
        isDark
          ? 'rounded-2xl bg-slate-900 px-4 py-4'
          : 'rounded-card bg-white p-4 shadow-card border border-border/80'
      }
    >
      <h3
        className={
          isDark ? 'text-sm font-semibold text-slate-300 mb-3' : 'text-sm font-semibold text-slate-900 mb-3'
        }
      >
        Прогресс по целям
      </h3>
      <div className="space-y-3">
        {data.goals.slice(0, 3).map((goal) => {
          const progress = goal.target <= 0 ? 100 : Math.max(0, Math.min(100, (Math.max(0, goal.current) / goal.target) * 100));
          return (
            <div key={goal.id} className="space-y-2">
              <p className={isDark ? 'font-medium text-white' : 'font-medium text-slate-900'}>
                {goal.title}
              </p>
              <div className="flex justify-between text-sm">
                <span className={isDark ? 'text-slate-400' : 'text-slate-600'}>
                  {formatMoney(goal.current)} ₽ / {formatMoney(goal.target)} ₽
                </span>
                <span className={isDark ? 'font-medium text-slate-300' : 'font-medium text-slate-700'}>
                  {Math.round(progress)}%
                </span>
              </div>
              <div className={`w-full rounded-full h-2 ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}>
                <div
                  className={`rounded-full h-2 transition-all ${isDark ? 'bg-blue-500' : 'bg-slate-800'}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
              {goal.months_to_goal !== null && goal.months_to_goal > 0 && (
                <p className={isDark ? 'text-xs text-slate-400' : 'text-xs text-muted'}>
                  Осталось: {formatMoney(goal.remaining)} ₽
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
