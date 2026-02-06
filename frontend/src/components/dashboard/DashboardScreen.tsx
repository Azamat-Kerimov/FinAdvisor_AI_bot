import { useState, useMemo } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { GoalsSummary } from './GoalsSummary';
import {
  useStats,
  getPreviousMonth,
  useMonthlyBalance,
  useCapitalSummary,
  useCapitalHistory,
  useConsultationHistory,
} from '@/hooks/useStats';
import type { CapitalHistoryItem } from '@/types/api';

const MONTH_NAMES = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

/** Сокращения месяцев (3 буквы) для подписей графиков */
const MONTH_SHORT = [
  'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек',
];

function toShortMonthLabel(label: string, monthNum?: number): string {
  if (monthNum != null && monthNum >= 1 && monthNum <= 12) return MONTH_SHORT[monthNum - 1];
  const firstWord = label.split(' ')[0];
  const idx = MONTH_NAMES.indexOf(firstWord);
  return idx >= 0 ? MONTH_SHORT[idx] : firstWord.slice(0, 3);
}

/** Варианты месяцев для выбора (последние 13: текущий + 12 прошлых) */
function getMonthOptions(): { month: number; year: number; label: string }[] {
  const options: { month: number; year: number; label: string }[] = [];
  const now = new Date();
  for (let i = 0; i <= 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const month = d.getMonth() + 1;
    const year = d.getFullYear();
    options.push({
      month,
      year,
      label: `${MONTH_NAMES[month - 1]} ${year}`,
    });
  }
  return options;
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(Math.round(value));
}

/** Краткая подпись для осей: "418 тыс.", "1.2 млн", "-139 тыс." */
function formatShortMoney(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '−' : '';
  if (abs >= 1_000_000) {
    const v = abs / 1_000_000;
    return `${sign}${v % 1 === 0 ? v : v.toFixed(1)} млн`;
  }
  if (abs >= 1_000) {
    const v = Math.round(abs / 1_000);
    return `${sign}${v} тыс.`;
  }
  return `${sign}${Math.round(abs)}`;
}

/** Только число для подписей на столбцах (размерность по оси): "+410", "-418", "1.2" */
function formatShortValueOnly(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '−' : value > 0 ? '+' : '';
  if (abs >= 1_000_000) {
    const v = abs / 1_000_000;
    return `${sign}${v % 1 === 0 ? v : v.toFixed(1)}`;
  }
  if (abs >= 1_000) {
    const v = Math.round(abs / 1_000);
    return `${sign}${v}`;
  }
  return `${sign}${Math.round(abs)}`;
}

/** Округление до «красивого» шага (1, 2, 5 * 10^n) */
function roundToNiceStep(x: number): number {
  if (x <= 0) return 1;
  const magnitude = Math.pow(10, Math.floor(Math.log10(x)));
  const normalized = x / magnitude;
  const stepMagnitude = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return magnitude * (stepMagnitude === 10 ? 10 : stepMagnitude);
}

/** Ось с шагами: 0, 3 сверху, 3 снизу (всего 7 подписей). maxTick >= maxAbs. */
function getNiceAxisRange(maxAbs: number): { maxTick: number; step: number; ticks: number[] } {
  if (maxAbs <= 0) return { maxTick: 1, step: 1, ticks: [0, 1, -1] };
  const rawStep = maxAbs / 3;
  const niceStep = roundToNiceStep(rawStep);
  const maxTick = Math.max(niceStep * 3, Math.ceil(maxAbs / niceStep) * niceStep);
  const ticks: number[] = [
    maxTick,
    maxTick - niceStep,
    maxTick - niceStep * 2,
    0,
    -niceStep,
    -niceStep * 2,
    -maxTick,
  ];
  return { maxTick, step: niceStep, ticks };
}

/** Светлая тема: обёртка страницы Главная */
const LIGHT_WRAPPER = 'min-h-full bg-slate-50 text-slate-900';

export function DashboardScreen() {
  const prev = getPreviousMonth();
  const [selectedMonth, setSelectedMonth] = useState(prev.month);
  const [selectedYear, setSelectedYear] = useState(prev.year);

  const { data: stats, loading: statsLoading, error: statsError } = useStats(selectedMonth, selectedYear);
  const { data: monthlyBalance, loading: monthlyLoading } = useMonthlyBalance();
  const { data: capitalSummary, loading: capitalSummaryLoading } = useCapitalSummary();
  const { data: capitalHistory, loading: capitalHistoryLoading } = useCapitalHistory();
  const { data: consultationHistory, loading: consultationLoading } = useConsultationHistory();

  const monthOptions = useMemo(getMonthOptions, []);

  return (
    <div className={LIGHT_WRAPPER}>
      <PageHeader title="Главная" />

      {/* Блок 1: Выбор месяца, расходы/доходы/разница, гистограмма разницы за год */}
      <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900">Денежный поток</h2>
          <div className="flex items-center h-9 rounded-lg border border-slate-300 bg-white pl-3 pr-8 text-slate-800 bg-no-repeat bg-[length:18px] bg-[right_6px_center]"
            style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2364748B'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")` }}
          >
            <select
              className="text-sm w-full min-w-0 h-full bg-transparent border-0 py-0 pl-0 pr-0 appearance-none cursor-pointer focus:outline-none focus:ring-0"
              value={`${selectedYear}-${selectedMonth}`}
              onChange={(e) => {
                const [y, m] = e.target.value.split('-').map(Number);
                setSelectedYear(y);
                setSelectedMonth(m);
              }}
            >
              {monthOptions.map((opt) => (
                <option key={`${opt.year}-${opt.month}`} value={`${opt.year}-${opt.month}`}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {statsLoading && (
          <div className="flex justify-center py-6">
            <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
          </div>
        )}
        {!statsLoading && statsError && (
          <p className="text-sm text-expense py-2">Не удалось загрузить данные</p>
        )}
        {!statsLoading && stats && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-lg p-3 border border-expense bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Расходы</p>
                <p className="text-sm font-semibold text-slate-900">{formatMoney(stats.total_expense)} ₽</p>
              </div>
              <div className="rounded-lg p-3 border border-income bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Доходы</p>
                <p className="text-sm font-semibold text-slate-900">{formatMoney(stats.total_income)} ₽</p>
              </div>
              <div
                className={`rounded-lg p-3 border ${
                  (stats.total_income - stats.total_expense) >= 0 ? 'bg-income/10 border-income/20' : 'bg-expense/10 border-expense/20'
                }`}
              >
                <p className="text-xs text-slate-600 mb-0.5">Разница</p>
                <p
                  className={`text-sm font-semibold ${
                    (stats.total_income - stats.total_expense) >= 0 ? 'text-income' : 'text-expense'
                  }`}
                >
                  {(stats.total_income - stats.total_expense) >= 0 ? '+' : '−'}
                  {formatMoney(Math.abs(stats.total_income - stats.total_expense))} ₽
                </p>
              </div>
            </div>

            <h3 className="text-sm font-medium text-slate-700 mb-2">Разница по месяцам (последний год)</h3>
            {monthlyLoading ? (
              <div className="h-32 flex items-center justify-center text-slate-400 text-sm">Загрузка...</div>
            ) : (() => {
              const filtered = monthlyBalance.filter((d) => d.income !== 0 || d.expense !== 0);
              return filtered.length === 0 ? (
                <p className="text-sm text-slate-500 py-4">Нет данных</p>
              ) : (
                <DifferenceBarChart data={filtered} />
              );
            })()}
          </>
        )}
      </Card>

      {/* Блок 2: Чистый капитал, активы/пассивы, гистограмма за 12 месяцев (как на образце) */}
      <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
        <h2 className="text-base font-semibold text-slate-900 mb-3">Чистый капитал</h2>
        {capitalSummaryLoading && (
          <div className="flex justify-center py-6">
            <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
          </div>
        )}
        {!capitalSummaryLoading && capitalSummary && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-lg p-3 border border-income bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Активы</p>
                <p className="text-sm font-semibold text-slate-900">{formatMoney(capitalSummary.assets)} ₽</p>
              </div>
              <div className="rounded-lg p-3 border border-expense bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Пассивы</p>
                <p className="text-sm font-semibold text-slate-900">{formatMoney(capitalSummary.liabilities)} ₽</p>
              </div>
              <div
                className={`rounded-lg p-3 border ${
                  capitalSummary.net >= 0 ? 'bg-income/10 border-income/20' : 'bg-expense/10 border-expense/20'
                }`}
              >
                <p className="text-xs text-slate-600 mb-0.5">Чистый капитал</p>
                <p
                  className={`text-sm font-semibold ${
                    capitalSummary.net >= 0 ? 'text-income' : 'text-expense'
                  }`}
                >
                  {capitalSummary.net >= 0 ? '+' : '−'}
                  {formatMoney(Math.abs(capitalSummary.net))} ₽
                </p>
              </div>
            </div>

            <h3 className="text-sm font-medium text-slate-700 mb-2">Финансовый путь</h3>
            {capitalHistoryLoading ? (
              <div className="h-48 flex items-center justify-center text-slate-400 text-sm">Загрузка...</div>
            ) : (() => {
              const filtered = capitalHistory.filter((d) => d.assets !== 0 || d.liabilities !== 0);
              return filtered.length === 0 ? (
                <p className="text-sm text-slate-500 py-4">Нет данных</p>
              ) : (
                <FinancialPathChart data={filtered} />
              );
            })()}
          </>
        )}
      </Card>

      {/* Блок 3: Прогресс по целям */}
      <div className="mb-4">
        <GoalsSummary variant="light" />
      </div>

      {/* Блок 4: Одна короткая версия последней консультации */}
      <Card className="p-4 bg-white border border-slate-200 shadow-card">
        <h2 className="text-base font-semibold text-slate-900 mb-3">Последние рекомендации</h2>
        {consultationLoading && (
          <div className="flex justify-center py-4">
            <div className="w-6 h-6 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
          </div>
        )}
        {!consultationLoading && (!consultationHistory || consultationHistory.length === 0) && (
          <p className="text-sm text-slate-500">Пока нет консультаций. Задайте вопрос в разделе «ИИ».</p>
        )}
        {!consultationLoading && consultationHistory && consultationHistory.length > 0 && (() => {
          const latest = consultationHistory[0];
          return (
            <div>
              <p className="text-xs text-slate-500 mb-1">
                {new Date(latest.date).toLocaleDateString('ru-RU', {
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
              </p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{latest.content}</p>
            </div>
          );
        })()}
      </Card>
    </div>
  );
}

/** Гистограмма: разница по месяцам. Ось с шагом кратным 1000/10k/100k/1M, подписи в тыс/млн, масштаб по оси. */
function DifferenceBarChart({
  data,
}: {
  data: { label: string; difference: number; month?: number }[];
}) {
  const values = data.map((d) => d.difference);
  const maxAbs = Math.max(1, ...values.map((v) => Math.abs(v)));
  const { maxTick, ticks } = getNiceAxisRange(maxAbs);
  const chartHeight = 140;
  const axisWidth = 52;

  const formatDiffLabel = (v: number) => formatShortValueOnly(v);

  return (
    <div className="flex gap-2">
      <div className="flex flex-col justify-between text-[10px] text-slate-500 shrink-0 py-0.5" style={{ width: axisWidth, height: chartHeight }}>
        {ticks.map((t, i) => (
          <span key={`${i}-${t}`}>{formatShortMoney(t)}</span>
        ))}
      </div>
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex gap-0.5" style={{ height: chartHeight }}>
          {data.map((d) => {
            const isPositive = d.difference >= 0;
            const heightPct = (Math.abs(d.difference) / maxTick) * 50;
            return (
              <div key={d.label} className="flex-1 min-w-0 flex flex-col justify-center items-center" style={{ minWidth: 0 }}>
                <div className="w-full flex-1 flex flex-col justify-end min-h-0 items-center">
                  <span className="text-[9px] font-medium text-slate-700 whitespace-nowrap z-10 w-full text-center">
                    {isPositive ? formatDiffLabel(d.difference) : ''}
                  </span>
                  <div
                    className={`w-full rounded-t min-h-[2px] ${isPositive ? 'bg-income' : 'bg-transparent'}`}
                    style={{ height: isPositive ? `${heightPct}%` : 0, maxHeight: '50%' }}
                  />
                </div>
                <div className="w-full flex-1 flex flex-col justify-start min-h-0 items-center">
                  <div
                    className={`w-full rounded-b min-h-[2px] ${!isPositive ? 'bg-expense' : 'bg-transparent'}`}
                    style={{ height: !isPositive ? `${heightPct}%` : 0, maxHeight: '50%' }}
                  />
                  <span className="text-[9px] font-medium text-slate-700 whitespace-nowrap z-10 w-full text-center">
                    {!isPositive ? formatDiffLabel(d.difference) : ''}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex gap-0.5 mt-1">
          {data.map((d) => (
            <div key={d.label} className="flex-1 min-w-0 text-center">
              <span className="text-[10px] text-slate-500 truncate block w-full">
                {toShortMonthLabel(d.label, (d as { month?: number }).month)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Гистограмма «Финансовый путь»: ось 0 + 3 сверху + 3 снизу, подписи только числа, линия NV. */
function FinancialPathChart({ data }: { data: CapitalHistoryItem[] }) {
  const maxAssets = Math.max(1, ...data.map((d) => d.assets));
  const maxLiabs = Math.max(1, ...data.map((d) => d.liabilities));
  const maxAbs = Math.max(maxAssets, maxLiabs);
  const { maxTick, ticks } = getNiceAxisRange(maxAbs);
  const chartHeight = 160;
  const axisWidth = 52;

  const assetRatio = (v: number) => Math.min(1, v / maxTick);
  const liabRatio = (v: number) => Math.min(1, v / maxTick);
  const netToY = (net: number): number => {
    if (net >= 0) return 50 - (net / maxTick) * 50;
    return 50 + (Math.abs(net) / maxTick) * 50;
  };

  return (
    <div className="flex gap-2">
      <div className="flex flex-col justify-between text-[10px] text-slate-500 shrink-0 py-0.5" style={{ width: axisWidth, height: chartHeight }}>
        {ticks.map((t, i) => (
          <span key={`${i}-${t}`}>{formatShortMoney(t)}</span>
        ))}
      </div>
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="relative flex gap-0.5" style={{ height: chartHeight }}>
          {data.map((d) => (
            <div key={d.label} className="flex-1 min-w-0 flex flex-col" style={{ minWidth: 0 }}>
              <div className="w-full relative flex flex-col flex-1 min-h-0">
                <div className="flex flex-col justify-end flex-1 items-center" style={{ height: '50%' }}>
                  <span className="text-[9px] font-medium text-slate-700 whitespace-nowrap z-10 w-full text-center">
                    {d.assets > 0 ? formatShortValueOnly(d.assets) : ''}
                  </span>
                  <div
                    className="w-full rounded-t bg-income/90 min-h-[2px]"
                    style={{ height: `${assetRatio(d.assets) * 100}%` }}
                  />
                </div>
                <div className="absolute left-0 right-0 border-t border-slate-300 border-dashed z-0" style={{ top: '50%' }} />
                <div className="flex flex-col justify-start flex-1 items-center" style={{ height: '50%' }}>
                  <div
                    className="w-full rounded-b bg-expense/90 min-h-[2px]"
                    style={{ height: `${liabRatio(d.liabilities) * 100}%` }}
                  />
                  <span className="text-[9px] font-medium text-slate-700 whitespace-nowrap z-10 w-full text-center">
                    {d.liabilities > 0 ? formatShortValueOnly(-d.liabilities) : ''}
                  </span>
                </div>
                <>
                  <span
                    className="absolute left-1/2 -translate-x-1/2 text-[8px] font-medium text-blue-600 whitespace-nowrap z-20"
                    style={{ top: `${netToY(d.net)}%`, marginTop: -18 }}
                  >
                    {formatShortValueOnly(d.net)}
                  </span>
                  <div
                    className="absolute left-1/2 w-2 h-2 rounded-full border-2 border-blue-600 bg-white z-20"
                    style={{ top: `${netToY(d.net)}%`, marginLeft: -4, marginTop: -4 }}
                  />
                </>
              </div>
            </div>
          ))}
          <svg
            className="absolute left-0 right-0 top-0 pointer-events-none z-[12]"
            style={{ height: chartHeight }}
            viewBox={`0 0 ${data.length} 100`}
            preserveAspectRatio="none"
          >
            <polyline
              fill="none"
              stroke="rgb(37 99 235)"
              strokeWidth="1"
              strokeDasharray="1.2 0.8"
              points={data.map((d, i) => `${i + 0.5} ${netToY(d.net)}`).join(' ')}
            />
          </svg>
        </div>
        <div className="flex gap-0.5 mt-1">
          {data.map((d) => (
            <div key={d.label} className="flex-1 min-w-0 text-center">
              <span className="text-[10px] text-slate-500 truncate block w-full">
                {toShortMonthLabel(d.label, d.month)}
              </span>
            </div>
          ))}
        </div>
        <div className="flex justify-center gap-4 mt-2 text-[10px] text-slate-500">
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded bg-income" /> Активы</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded bg-expense" /> Пассивы</span>
          <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full border-2 border-blue-600 bg-white" /> NV</span>
        </div>
      </div>
    </div>
  );
}
