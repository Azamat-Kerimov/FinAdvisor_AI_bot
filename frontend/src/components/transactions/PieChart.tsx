/** Круговая диаграмма для расходов или доходов по категориям */
function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(value));
}

interface PieChartProps {
  data: Record<string, number>;
  total: number;
  title: string;
  colors?: string[];
}

const DEFAULT_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899',
  '#06B6D4', '#84CC16', '#F97316', '#6366F1', '#14B8A6', '#A855F7',
];

export function PieChart({ data, total, title, colors = DEFAULT_COLORS }: PieChartProps) {
  const entries = Object.entries(data)
    .map(([name, amount]) => ({ name, amount: amount as number }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, 8);

  if (total === 0 || entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <div className="w-32 h-32 rounded-full bg-slate-200 flex items-center justify-center">
          <span className="text-slate-400 text-sm">Нет данных</span>
        </div>
        <p className="mt-4 text-sm font-semibold text-slate-900">{title}</p>
      </div>
    );
  }

  const r = 50;
  const center = 50;
  let currentAngle = -90;

  function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function describeArc(cx: number, cy: number, R: number, startAngle: number, endAngle: number) {
    const start = polarToCartesian(cx, cy, R, startAngle);
    const end = polarToCartesian(cx, cy, R, endAngle);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${start.x} ${start.y} A ${R} ${R} 0 ${largeArc} 1 ${end.x} ${end.y} Z`;
  }

  const segments = entries.map((entry, i) => {
    const percent = (entry.amount / total) * 100;
    const angle = (percent / 100) * 360;
    const startAngle = currentAngle;
    const endAngle = currentAngle + angle;
    currentAngle = endAngle;
    return {
      ...entry,
      percent,
      path: describeArc(center, center, r, startAngle, endAngle),
      color: colors[i % colors.length],
    };
  });

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 100 100" className="w-full max-w-[200px]" style={{ width: 200, height: 200 }}>
        {segments.map((seg, i) => (
          <path key={i} d={seg.path} fill={seg.color} />
        ))}
      </svg>
      <p className="mt-4 text-sm font-semibold text-slate-900">{title}</p>
      <div className="mt-3 space-y-1.5 w-full max-w-[280px]">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <span
                className="h-3 w-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: seg.color }}
              />
              <span className="truncate text-slate-700">{seg.name}</span>
            </div>
            <span className="ml-2 font-medium text-slate-900 whitespace-nowrap">
              {formatMoney(seg.amount)} ₽
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
