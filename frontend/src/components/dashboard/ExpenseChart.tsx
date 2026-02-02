import { Card } from '@/components/ui/Card';
import type { Stats } from '@/types/api';

interface ExpenseChartProps {
  data: Stats;
}

export function ExpenseChart({ data }: ExpenseChartProps) {
  const expenses = data.expense_by_category || {};
  const entries = Object.entries(expenses)
    .map(([name, amount]) => ({ name, amount: amount as number }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, 5);

  const total = entries.reduce((sum, e) => sum + e.amount, 0);
  if (total === 0) return null;

  function formatMoney(value: number): string {
    return new Intl.NumberFormat('ru-RU').format(Math.round(value));
  }

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold text-slate-900 mb-3">Топ расходов</h3>
      <div className="space-y-2">
        {entries.map(({ name, amount }) => {
          const percent = (amount / total) * 100;
          return (
            <div key={name} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-slate-700">{name}</span>
                <span className="font-medium text-slate-900">{formatMoney(amount)} ₽</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-1.5">
                <div
                  className="bg-slate-800 h-1.5 rounded-full transition-all"
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
