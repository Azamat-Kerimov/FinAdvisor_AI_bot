import { useState, useMemo } from 'react';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { ExampleReportImage } from '@/components/ui/ExampleReportImage';
import { GoalsSummary } from './GoalsSummary';
import {
  useStats,
  getPreviousMonth,
  useMonthlyBalance,
  useCapitalSummary,
  useCapitalHistory,
  useConsultationHistory,
  useBenchmarks,
  useProgressVsSelf,
  useOnboardingProgress,
  useAlerts,
  useFocusGoal,
  useBadges,
} from '@/hooks/useStats';
import { apiRequest } from '@/lib/api';
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

const ONBOARDING_STORAGE_KEY = 'finadvisor_onboarding_seen';

export function DashboardScreen() {
  const prev = getPreviousMonth();
  const [selectedMonth, setSelectedMonth] = useState(prev.month);
  const [selectedYear, setSelectedYear] = useState(prev.year);
  const [onboardingSeen, setOnboardingSeen] = useState(() =>
    typeof localStorage !== 'undefined' && localStorage.getItem(ONBOARDING_STORAGE_KEY) === 'true'
  );
  const [benchmarksHelpOpen, setBenchmarksHelpOpen] = useState(false);
  const [progressHelpOpen, setProgressHelpOpen] = useState(false);
  const [capitalHelpOpen, setCapitalHelpOpen] = useState(false);

  const { data: stats, loading: statsLoading, error: statsError } = useStats(selectedMonth, selectedYear);
  const { data: monthlyBalance, loading: monthlyLoading } = useMonthlyBalance();
  const { data: capitalSummary, loading: capitalSummaryLoading } = useCapitalSummary();
  const { data: capitalHistory, loading: capitalHistoryLoading } = useCapitalHistory();
  const { data: consultationHistory, loading: consultationLoading } = useConsultationHistory();
  const { data: benchmarks, loading: benchmarksLoading } = useBenchmarks();
  const { data: progressVsSelf, loading: progressVsSelfLoading } = useProgressVsSelf();
  const { data: alertsData, loading: alertsLoading } = useAlerts();
  const { data: focusGoal, loading: focusGoalLoading, refetch: refetchFocusGoal } = useFocusGoal();
  const { data: badgesData, loading: badgesLoading } = useBadges();
  const { data: onboardingProgress, loading: onboardingProgressLoading } = useOnboardingProgress();

  const monthOptions = useMemo(getMonthOptions, []);

  async function markFocusGoalAchieved(goalId: number) {
    try {
      await apiRequest(`/api/focus-goal/${goalId}`, { method: 'PATCH' });
      refetchFocusGoal();
    } catch (e) {
      console.error(e);
    }
  }

  function dismissOnboarding() {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true');
    }
    setOnboardingSeen(true);
  }

  return (
    <div className={LIGHT_WRAPPER}>
      <PageHeader title="Главная" />

      {/* Онбординг: что это за приложение и как пользоваться */}
      {!onboardingSeen && (
        <Card className="p-4 mb-4 bg-white border-2 border-slate-200 shadow-card">
          <h2 className="text-lg font-bold text-slate-900 mb-3">Добро пожаловать!</h2>
          <p className="text-sm text-slate-800 mb-3 leading-relaxed">
            FinAdvisor — ваш персональный финансовый помощник. Здесь вы ведёте учёт денег, ставите цели и получаете консультации ИИ на основе ваших реальных данных (транзакции, активы, долги).
          </p>
          <p className="text-sm font-medium text-slate-900 mb-2">Что умеет приложение:</p>
          <ul className="text-sm text-slate-800 space-y-2 mb-4 list-disc list-inside leading-relaxed">
            <li><strong>Транзакции</strong> — добавляйте доходы и расходы вручную или загружайте выписку Excel из банка (Сбер, Т‑Банк).</li>
            <li><strong>Капитал</strong> — указывайте активы (счета, вклады, акции) и долги (кредиты, рассрочки).</li>
            <li><strong>Цели</strong> — задавайте финансовые цели; прогресс считается автоматически по ликвидному капиталу.</li>
            <li><strong>Консультации ИИ</strong> — получайте персональные рекомендации и план действий по вашим цифрам (лимит сессий в месяц).</li>
            <li><strong>Профиль</strong> — пол, возраст, семья, город для более точных советов.</li>
          </ul>
          <p className="text-sm text-slate-700 mb-4">Подробнее — во вкладке «Помощь» внизу экрана.</p>
          <p className="text-sm font-medium text-slate-900 mb-2">Примеры отчётов:</p>
          <div className="grid grid-cols-1 gap-3 mb-4">
            <div className="rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
              <p className="text-xs font-medium text-slate-700 p-2">Денежный поток</p>
              <ExampleReportImage
                src="/examples/cashflow.png"
                alt="Пример: денежный поток — расходы, доходы, разница, график по месяцам"
                className="w-full h-auto object-contain max-h-48"
              />
            </div>
            <div className="rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
              <p className="text-xs font-medium text-slate-700 p-2">Чистый капитал и финансовый путь</p>
              <ExampleReportImage
                src="/examples/capital.png"
                alt="Пример: чистый капитал — активы, пассивы, график динамики"
                className="w-full h-auto object-contain max-h-48"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={dismissOnboarding}
            className="w-full py-2.5 px-4 rounded-button bg-slate-800 text-white font-medium text-sm hover:bg-slate-700 transition-colors"
          >
            Понятно
          </button>
        </Card>
      )}

      {/* Пайплайн онбординга: после «Понятно» */}
      {onboardingSeen && !onboardingProgressLoading && onboardingProgress && (
        <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
          <h2 className="text-base font-semibold text-slate-900 mb-3">Ваш прогресс</h2>
          <div className="space-y-3">
            {[
              { done: onboardingProgress.has_transactions, label: 'Добавьте или загрузите транзакции', sub: 'Транзакции' },
              { done: onboardingProgress.has_capital, label: 'Добавьте активы и долги', sub: 'Капитал' },
              { done: onboardingProgress.has_profile, label: 'Заполните профиль', sub: 'Профиль' },
              { done: onboardingProgress.has_consultation, label: 'Получите консультацию ИИ', sub: 'ИИ' },
              { done: onboardingProgress.has_transactions && onboardingProgress.has_capital && onboardingProgress.has_profile && onboardingProgress.has_consultation, label: 'Наслаждайтесь', sub: '' },
            ].map((step, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-lg border border-slate-100">
                <div
                  className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                    step.done ? 'bg-green-500 text-white' : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  {step.done ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <span className="text-sm font-medium">{i + 1}</span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className={`text-sm font-medium ${step.done ? 'text-slate-700' : 'text-slate-900'}`}>{step.label}</p>
                  {step.sub && <p className="text-xs text-slate-500">{step.sub}</p>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Цель месяца (фокус от ИИ) */}
      {!focusGoalLoading && focusGoal && (
        <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
          <h2 className="text-base font-semibold text-slate-900 mb-2">Цель этого месяца</h2>
          {focusGoal.achieved_at ? (
            <div className="p-3 bg-green-50 border border-green-200 rounded-button">
              <p className="text-sm font-medium text-green-800">🎉 Цель достигнута!</p>
              <p className="text-sm text-green-700 mt-1">{focusGoal.title}</p>
            </div>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm text-slate-700 flex-1">{focusGoal.title}</p>
              <button
                type="button"
                onClick={() => markFocusGoalAchieved(focusGoal.id)}
                className="shrink-0 py-2 px-3 rounded-button bg-slate-800 text-white text-sm font-medium hover:bg-slate-700"
              >
                Отметить выполненным
              </button>
            </div>
          )}
        </Card>
      )}

      {/* Мягкие алерты */}
      {!alertsLoading && alertsData && alertsData.alerts.length > 0 && (
        <Card className="p-4 mb-4 bg-amber-50 border border-amber-200 shadow-card">
          <h2 className="text-base font-semibold text-amber-900 mb-2">Обратите внимание</h2>
          <ul className="space-y-1 text-sm text-amber-800">
            {alertsData.alerts.map((a, i) => (
              <li key={i}>{a.text}</li>
            ))}
          </ul>
        </Card>
      )}

      {/* Бейджи прогресса */}
      {!badgesLoading && badgesData && badgesData.badges.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {badgesData.badges.map((b) => (
            <span
              key={b.id}
              className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200"
            >
              ✓ {b.label}
            </span>
          ))}
        </div>
      )}

      {/* Блок 1: Денежный поток + Прогресс относительно себя + Сравнение с целевыми нормами (визуально один блок) */}
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
                <p className="text-xs font-semibold text-slate-900 break-all">{formatMoney(stats.total_expense)} ₽</p>
              </div>
              <div className="rounded-lg p-3 border border-income bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Доходы</p>
                <p className="text-xs font-semibold text-slate-900 break-all">{formatMoney(stats.total_income)} ₽</p>
              </div>
              <div
                className={`rounded-lg p-3 border ${
                  (stats.total_income - stats.total_expense) >= 0 ? 'bg-income/10 border-income/20' : 'bg-expense/10 border-expense/20'
                }`}
              >
                <p className="text-xs text-slate-600 mb-0.5">Разница</p>
                <p
                  className={`text-xs font-semibold break-all ${
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

        {/* Прогресс относительно себя: топ-3, в том же блоке */}
        {!progressVsSelfLoading && progressVsSelf && progressVsSelf.categories.length > 0 && (
          <>
            <hr className="my-4 border-slate-200" />
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-base font-semibold text-slate-900">Прогресс относительно себя</h3>
              <button
                type="button"
                onClick={() => setProgressHelpOpen(!progressHelpOpen)}
                className="rounded-full w-7 h-7 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
                title="Как читать отчёт"
              >
                ?
              </button>
            </div>
            {progressHelpOpen && (
              <div className="mb-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700">
                <p className="font-medium mb-1">Как читать отчёт</p>
                <p>«В ср. в мес.» — среднее в месяц за последние 12 месяцев по категории расходов (без учёта переводов людям и от людей). «Последний месяц» — сумма за последний календарный месяц. Показаны топ-3 категории с наибольшей разницей: сначала где расходы выросли сильнее всего, затем где снизились.</p>
              </div>
            )}
            <p className="text-xs text-slate-500 mb-2">
              {progressVsSelf.period_before} → {progressVsSelf.period_now}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-slate-700 border-collapse">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 pr-2 font-medium text-slate-600">Категория</th>
                    <th className="text-right py-2 px-2 font-medium text-slate-600">В ср. в мес.</th>
                    <th className="text-right py-2 px-2 font-medium text-slate-600">Последний месяц</th>
                    <th className="text-right py-2 pl-2 font-medium text-slate-600">Разница</th>
                  </tr>
                </thead>
                <tbody>
                  {progressVsSelf.categories.map((c) => {
                    const diff = c.now - c.before;
                    return (
                      <tr key={c.category} className="border-b border-slate-100">
                        <td className="py-2 pr-2">{c.category}</td>
                        <td className="text-right py-2 px-2 whitespace-nowrap">{formatShortMoney(c.before)}</td>
                        <td className="text-right py-2 px-2 whitespace-nowrap">{formatShortMoney(c.now)}</td>
                        <td className={`text-right py-2 pl-2 whitespace-nowrap ${diff > 0 ? 'text-expense' : diff < 0 ? 'text-income' : ''}`}>
                          {diff > 0 ? '+' : diff < 0 ? '−' : ''}{formatShortMoney(Math.abs(diff))}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Сравнение с целевыми нормами: в том же блоке, таблица У вас / Цель */}
        {!benchmarksLoading && benchmarks && benchmarks.total_income > 0 && benchmarks.savings != null && (
          <>
            <hr className="my-4 border-slate-200" />
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-base font-semibold text-slate-900">Сравнение с целевыми нормами</h3>
              <button
                type="button"
                onClick={() => setBenchmarksHelpOpen(!benchmarksHelpOpen)}
                className="rounded-full w-7 h-7 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
                title="Как читать отчёт"
              >
                ?
              </button>
            </div>
            {benchmarksHelpOpen && (
              <div className="mb-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700">
                <p className="font-medium mb-1">Как читать отчёт</p>
                <p className="mb-2">«У вас» — ваша фактическая доля в процентах от дохода.<br />«Цель» — рекомендуемый диапазон значений.</p>
                <p className="mb-2">Доход — это налогооблагаемый доход: зарплата, дивиденды и купоны, прочие поступления.<br />Если данных меньше чем за год, расчёт делается за доступный период.</p>
                <p>В отчёте отображаются:<br />• Сбережения<br />• Категории, где рекомендуемая норма превышена.</p>
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-slate-700 border-collapse">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 pr-2 font-medium text-slate-600">Категория</th>
                    <th className="text-right py-2 px-2 font-medium text-slate-600">У вас</th>
                    <th className="text-right py-2 pl-2 font-medium text-slate-600">Цель</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ...(benchmarks.savings ? [{ name: 'Сбережения' as const, ...benchmarks.savings }] : []),
                    ...benchmarks.categories,
                  ].map((row) => {
                    const isSavings = row.name === 'Сбережения';
                    const belowTarget = row.user_pct < row.target_low;
                    const aboveTarget = row.user_pct > row.target_high;
                    const isBad = isSavings ? belowTarget : aboveTarget;
                    return (
                      <tr key={row.name} className="border-b border-slate-100">
                        <td className="py-2 pr-2">{row.name}</td>
                        <td className={`text-right py-2 px-2 ${isBad ? 'text-expense font-medium' : ''}`}>
                          {row.user_pct}%
                        </td>
                        <td className="text-right py-2 pl-2 text-slate-600">
                          {row.target_low}–{row.target_high}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      {/* Блок 2: Чистый капитал, активы/пассивы, гистограмма за 12 месяцев (как на образце) */}
      <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-base font-semibold text-slate-900">Чистый капитал</h2>
          <button
            type="button"
            onClick={() => setCapitalHelpOpen(!capitalHelpOpen)}
            className="rounded-full w-7 h-7 flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200 shrink-0"
            title="Пояснения"
          >
            ?
          </button>
        </div>
        {capitalHelpOpen && (
          <div className="mb-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700">
            <p className="font-medium mb-1">Как читать блок</p>
            <p>Активы — сумма всех активов (счета, вклады, акции, облигации, наличные и т.д.) по последним введённым значениям. Пассивы — сумма долгов (кредиты, займы, рассрочки). Чистый капитал = Активы − Пассивы. График «Финансовый путь» показывает, как активы, пассивы и чистый капитал менялись по месяцам.</p>
          </div>
        )}
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
                <p className="text-xs font-semibold text-slate-900 break-all">{formatMoney(capitalSummary.assets)} ₽</p>
              </div>
              <div className="rounded-lg p-3 border border-expense bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Пассивы</p>
                <p className="text-xs font-semibold text-slate-900 break-all">{formatMoney(capitalSummary.liabilities)} ₽</p>
              </div>
              <div
                className={`rounded-lg p-3 border ${
                  capitalSummary.net >= 0 ? 'bg-income/10 border-income/20' : 'bg-expense/10 border-expense/20'
                }`}
              >
                <p className="text-xs text-slate-600 mb-0.5">Чистый капитал</p>
                <p
                  className={`text-xs font-semibold break-all ${
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

/** Гистограмма: разница по месяцам. Высота столбца привязана к значению по оси Y; подписи у концов столбцов. */
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
            const heightPctOfHalf = (Math.abs(d.difference) / maxTick) * 100;
            return (
              <div key={d.label} className="flex-1 min-w-0 flex flex-col justify-center items-center" style={{ minWidth: 0 }}>
                <div className="w-full flex-1 flex flex-col justify-end min-h-0 items-center">
                  <span className="text-[9px] font-medium text-slate-700 whitespace-nowrap z-10 w-full text-center">
                    {isPositive ? formatDiffLabel(d.difference) : ''}
                  </span>
                  <div
                    className={`w-full rounded-t min-h-[2px] ${isPositive ? 'bg-income' : 'bg-transparent'}`}
                    style={{ height: isPositive ? `${heightPctOfHalf}%` : 0, maxHeight: '100%' }}
                  />
                </div>
                <div className="w-full flex-1 flex flex-col justify-start min-h-0 items-center">
                  <div
                    className={`w-full rounded-b min-h-[2px] ${!isPositive ? 'bg-expense' : 'bg-transparent'}`}
                    style={{ height: !isPositive ? `${heightPctOfHalf}%` : 0, maxHeight: '100%' }}
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
                {(() => {
                  const netY = netToY(d.net);
                  const assetTopPct = 50 - assetRatio(d.assets) * 50;
                  const noDebt = d.liabilities <= 0;
                  const nvOverlapsAssets = noDebt && netY > 10 && netY < assetTopPct + 14;
                  const labelOffset = nvOverlapsAssets ? -22 : -18;
                  return (
                    <>
                      <span
                        className="absolute left-1/2 text-[8px] font-medium text-blue-600 whitespace-nowrap z-20"
                        style={{ top: `${netY}%`, marginTop: labelOffset, transform: 'translate(-50%, 0)' }}
                      >
                        {formatShortValueOnly(d.net)}
                      </span>
                      <div
                        className="absolute left-1/2 w-2 h-2 rounded-full border-2 border-blue-600 bg-white z-20"
                        style={{ top: `${netY}%`, marginLeft: -4, marginTop: -4 }}
                      />
                    </>
                  );
                })()}
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
