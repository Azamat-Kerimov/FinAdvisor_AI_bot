/** Круговая диаграмма: доходы / расходы / остаток. Центр — остаток (₽). */
function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(value));
}

interface DonutChartProps {
  income: number;
  expense: number;
  balance: number;
  size?: number;
}

export function DonutChart({ income, expense, balance, size = 200 }: DonutChartProps) {
  const total = income + expense + Math.max(0, balance);
  const incomeShare = total > 0 ? income / total : 0;
  const expenseShare = total > 0 ? expense / total : 0;
  const balanceShare = total > 0 ? Math.max(0, balance) / total : 0;

  const r = 42;
  const R = 50;
  const center = 50;

  function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function describeArc(cx: number, cy: number, R: number, startAngle: number, endAngle: number) {
    const start = polarToCartesian(cx, cy, R, endAngle);
    const end = polarToCartesian(cx, cy, R, startAngle);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${R} ${R} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  }

  function segmentPath(a0Deg: number, a1Deg: number): string {
    const startOuter = polarToCartesian(center, center, R, a0Deg);
    const endOuter = polarToCartesian(center, center, R, a1Deg);
    const startInner = polarToCartesian(center, center, r, a0Deg);
    const endInner = polarToCartesian(center, center, r, a1Deg);
    const large = a1Deg - a0Deg > 180 ? 1 : 0;
    return (
      `M ${startOuter.x} ${startOuter.y} A ${R} ${R} 0 ${large} 1 ${endOuter.x} ${endOuter.y} ` +
      `L ${endInner.x} ${endInner.y} A ${r} ${r} 0 ${large} 0 ${startInner.x} ${startInner.y} Z`
    );
  }

  let a0 = 0;
  const segments: { path: string; fill: string }[] = [];
  if (incomeShare > 0.005) {
    const a1 = a0 + incomeShare * 360;
    segments.push({ path: segmentPath(a0, a1), fill: '#10B981' });
    a0 = a1;
  }
  if (expenseShare > 0.005) {
    const a1 = a0 + expenseShare * 360;
    segments.push({ path: segmentPath(a0, a1), fill: '#EF4444' });
    a0 = a1;
  }
  if (balanceShare > 0.005) {
    const a1 = a0 + balanceShare * 360;
    segments.push({ path: segmentPath(a0, a1), fill: '#3B82F6' });
  }

  const hasData = total > 0;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 100 100" className="w-full max-w-[220px]" style={{ width: size, height: size }}>
        {hasData ? (
          <>
            {segments.map((s, i) => (
              <path key={i} d={s.path} fill={s.fill} />
            ))}
            <circle cx={center} cy={center} r={r - 4} fill="rgb(30 41 59)" />
            <text
              x={center}
              y={center - 6}
              textAnchor="middle"
              className="fill-slate-400 text-[8px] font-medium"
            >
              Остаток
            </text>
            <text
              x={center}
              y={center + 8}
              textAnchor="middle"
              className="fill-white text-sm font-bold"
            >
              {formatMoney(Math.max(0, balance))} ₽
            </text>
          </>
        ) : (
          <>
            <circle cx={center} cy={center} r={R} fill="rgb(51 65 85)" />
            <circle cx={center} cy={center} r={r} fill="rgb(30 41 59)" />
            <text x={center} y={center} textAnchor="middle" className="fill-slate-500 text-xs">
              Нет данных
            </text>
          </>
        )}
      </svg>
    </div>
  );
}
