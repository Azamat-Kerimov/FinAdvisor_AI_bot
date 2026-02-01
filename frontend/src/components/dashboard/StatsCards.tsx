import { Card } from '@/components/ui/Card';
import type { Stats } from '@/types/api';

function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(value));
}

interface StatsCardsProps {
  data: Stats;
  /** Период для подписи (например «1–9 июля»). Масштабирование: передавать с сервера или из контекста календаря. */
  periodLabel?: string;
}

/**
 * Три карточки потоков: Доходы / Расходы / Остаток.
 * Референс: Monarch cash flow — пастельные фоны по смыслу (зелёный/розовый/голубой).
 */
export function StatsCards({ data, periodLabel }: StatsCardsProps) {
  const income = data.total_income ?? 0;
  const expense = data.total_expense ?? 0;
  const savings = Math.max(0, income - expense);

  return (
    <div className="space-y-3">
      {periodLabel && (
        <p className="text-sm text-muted mb-1">{periodLabel}</p>
      )}
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
