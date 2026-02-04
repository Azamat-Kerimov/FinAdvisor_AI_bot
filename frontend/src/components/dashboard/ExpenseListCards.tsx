import type { Stats } from '@/types/api';

function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(value));
}

const CATEGORY_ICONS: Record<string, string> = {
  'Прочие расходы': '📦',
  'Прочие доходы': '📥',
  'Супермаркеты': '🛒',
  'Рестораны и кафе': '🍽️',
  'Транспорт': '🚗',
  'Здоровье': '💊',
  'Развлечения': '🎬',
  'Жильё': '🏠',
  'Одежда': '👕',
};

function getIcon(name: string): string {
  return CATEGORY_ICONS[name] ?? '📌';
}

interface ExpenseListCardsProps {
  data: Stats;
}

export function ExpenseListCards({ data }: ExpenseListCardsProps) {
  const expenses = data.expense_by_category || {};
  const entries = Object.entries(expenses)
    .map(([name, amount]) => ({ name, amount: amount as number }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, 6);

  const total = entries.reduce((sum, e) => sum + e.amount, 0);
  if (total === 0) return null;

  return (
    <div className="space-y-2">
      {entries.map(({ name, amount }) => {
        const percent = total > 0 ? Math.round((amount / total) * 100) : 0;
        return (
          <div
            key={name}
            className="flex items-center gap-3 rounded-xl bg-slate-800/80 px-4 py-3"
          >
            <span className="text-xl leading-none">{getIcon(name)}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-white">{name}</p>
              <p className="text-xs text-slate-400">{percent}% от расходов</p>
            </div>
            <div className="text-right">
              <p className="font-semibold text-white">{formatMoney(amount)} ₽</p>
              <p className="text-xs text-slate-400">{percent}%</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
