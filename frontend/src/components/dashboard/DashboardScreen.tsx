import { PageHeader } from '@/components/layout/PageHeader';
import { WelcomeCard } from './WelcomeCard';
import { InsightBlock } from './InsightBlock';
import { GoalsSummary } from './GoalsSummary';
import { useStats } from '@/hooks/useStats';
import { DonutChart } from './DonutChart';
import { ExpenseListCards } from './ExpenseListCards';

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
      <PageHeader
        title="Денежный поток"
        subtitle={currentMonthLabel()}
      />
      {loading && (
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <div className="w-10 h-10 border-2 border-slate-500 border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-sm">Загрузка...</p>
        </div>
      )}
      {!loading && error && <WelcomeCard />}
      {!loading && data && (
        <>
          {/* Тёмный блок в стиле Revolut: круговая диаграмма + список по категориям */}
          <div className="rounded-2xl bg-slate-900 px-4 py-6 text-white">
            <div className="mb-6">
              <DonutChart
                income={data.total_income ?? 0}
                expense={data.total_expense ?? 0}
                balance={Math.max(0, (data.total_income ?? 0) - (data.total_expense ?? 0))}
                size={220}
              />
            </div>
            <div className="mb-4 flex justify-center gap-6 text-xs">
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                Доходы
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                Расходы
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                Остаток
              </span>
            </div>
            <h3 className="mb-3 text-sm font-semibold text-slate-300">Расходы по категориям</h3>
            <ExpenseListCards data={data} />
          </div>

          <div className="mt-4">
            <GoalsSummary variant="dark" />
          </div>
          <InsightBlock data={data} />
        </>
      )}
    </>
  );
}
