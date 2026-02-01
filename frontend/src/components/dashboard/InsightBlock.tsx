import { Card } from '@/components/ui/Card';
import type { Stats } from '@/types/api';

interface InsightBlockProps {
  data: Stats;
}

/** Краткий инсайт по топу расходов и рекомендация по резерву. Масштабирование: вынести в отдельный виджет при росте контента. */
export function InsightBlock({ data }: InsightBlockProps) {
  const { insight, reserve_recommended } = data;
  const reserve = reserve_recommended ?? 0;
  const formatMoney = (v: number) => new Intl.NumberFormat('ru-RU').format(Math.round(v));

  if (!insight && reserve <= 0) return null;

  return (
    <Card className="p-4 mt-4">
      {insight && (
        <p className="text-sm text-slate-600 leading-relaxed">{insight}</p>
      )}
      {reserve > 0 && (
        <p className="text-sm text-muted mt-2">
          Рекомендуемый резервный фонд: {formatMoney(reserve)} ₽
        </p>
      )}
    </Card>
  );
}
