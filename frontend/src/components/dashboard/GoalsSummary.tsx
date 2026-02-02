import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
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

export function GoalsSummary() {
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

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold text-slate-900 mb-3">Прогресс по целям</h3>
      <div className="space-y-3">
        {data.goals.slice(0, 3).map((goal) => {
          const progress = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;
          return (
            <div key={goal.id} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-slate-700 font-medium">{goal.title}</span>
                <span className="text-slate-600">
                  {formatMoney(goal.current)} / {formatMoney(goal.target)} ₽
                </span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div
                  className="bg-slate-800 h-2 rounded-full transition-all"
                  style={{ width: `${Math.min(100, progress)}%` }}
                />
              </div>
              {goal.months_to_goal !== null && goal.months_to_goal > 0 && (
                <p className="text-xs text-muted">
                  Осталось: {formatMoney(goal.remaining)} ₽ (~{goal.months_to_goal} мес.)
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
