import { PageHeader } from '@/components/layout/PageHeader';
import { StatsCards } from './StatsCards';
import { WelcomeCard } from './WelcomeCard';
import { InsightBlock } from './InsightBlock';
import { useStats } from '@/hooks/useStats';

/** Текущий месяц в формате «1–30 июля» для подписи. Масштабирование: получать с API или из выбора периода. */
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
