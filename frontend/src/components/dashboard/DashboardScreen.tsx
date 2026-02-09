import { useState, useMemo, useRef } from 'react';
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
  useOnboardingProgress,
  useAlerts,
  useFocusGoal,
  useBadges,
} from '@/hooks/useStats';
import { apiRequest } from '@/lib/api';
import type { CapitalHistoryItem } from '@/types/api';
import type { NavScreen } from '@/components/layout/BottomNav';
import { usePullToRefresh } from '@/hooks/usePullToRefresh';
import { ShareButton } from '@/components/ui/ShareButton';
import { ONBOARDING_STORAGE_KEY, PROGRESS_CLOSED_KEY, isOnboardingSeen, isProgressClosed, markOnboardingSeen } from '@/lib/onboarding';

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

/** Обёртка страницы Главная (светлая и тёмная тема) */
const LIGHT_WRAPPER = 'min-h-full bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-200';

/** Подсказка к алерту о резервном фонде */
const RESERVE_ALERT_TOOLTIP =
  'Резерв считается так: ликвидный капитал (активы: депозиты, счета, наличные и т.д. минус ликвидные долги) делим на средние месячные расходы за последние 3 месяца. Рекомендуется иметь запас на 3–6 месяцев расходов.';

interface DashboardScreenProps {
  onNavigate?: (screen: NavScreen) => void;
}

export function DashboardScreen({ onNavigate }: DashboardScreenProps) {
  const prev = getPreviousMonth();
  const [selectedMonth, setSelectedMonth] = useState(prev.month);
  const [selectedYear, setSelectedYear] = useState(prev.year);
  const [onboardingSeen, setOnboardingSeen] = useState(isOnboardingSeen);
  const [progressClosed, setProgressClosed] = useState(isProgressClosed);
  const [benchmarksHelpOpen, setBenchmarksHelpOpen] = useState(false);
  const [capitalHelpOpen, setCapitalHelpOpen] = useState(false);

  const { data: stats, loading: statsLoading, error: statsError, refetch: refetchStats } = useStats(selectedMonth, selectedYear);
  const { data: monthlyBalance, loading: monthlyLoading } = useMonthlyBalance();
  const { data: capitalSummary, loading: capitalSummaryLoading } = useCapitalSummary();
  const { data: capitalHistory, loading: capitalHistoryLoading } = useCapitalHistory();
  const { data: consultationHistory, loading: consultationLoading } = useConsultationHistory();
  const { data: benchmarks, loading: benchmarksLoading } = useBenchmarks();
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
    markOnboardingSeen();
    setOnboardingSeen(true);
  }

  const { pullProps, pullY, isRefreshing } = usePullToRefresh(() => refetchStats());
  const cashFlowCardRef = useRef<HTMLDivElement>(null);

  return (
    <div className={LIGHT_WRAPPER} {...pullProps}>
      {(pullY > 0 || isRefreshing) && (
        <div className="flex justify-center py-2 text-sm text-slate-500 dark:text-slate-400">
          {isRefreshing ? 'Обновление...' : 'Потяните для обновления'}
        </div>
      )}
      <PageHeader title="Главная" />

      {/* Онбординг: что это за приложение и как пользоваться */}
      {!onboardingSeen && (
        <Card className="p-4 mb-4 bg-white border-2 border-slate-200 shadow-card">
          <h2 className="text-sm font-bold text-slate-900 mb-3">Добро пожаловать!</h2>
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

      {/* Пайплайн онбординга: после «Понятно»; скрываем карточку, если всё пройдено и нажали «Закрыть» */}
      {onboardingSeen && !onboardingProgressLoading && onboardingProgress && (() => {
        const allDone =
          onboardingProgress.has_transactions &&
          onboardingProgress.has_capital &&
          onboardingProgress.has_profile &&
          onboardingProgress.has_consultation;
        if (allDone && progressClosed) return null;
        return (
          <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
            <h2 className="text-sm font-bold text-slate-900 mb-3">Ваш прогресс</h2>
            <div className="space-y-3">
              {[
                { done: onboardingProgress.has_transactions, label: 'Добавьте или загрузите транзакции', sub: 'Транзакции', screen: 'finance' as NavScreen },
                { done: onboardingProgress.has_capital, label: 'Добавьте активы и долги', sub: 'Капитал', screen: 'finance' as NavScreen },
                { done: onboardingProgress.has_profile, label: 'Заполните профиль', sub: 'Профиль', screen: 'profile' as NavScreen },
                { done: onboardingProgress.has_consultation, label: 'Получите консультацию ИИ', sub: 'ИИ', screen: 'consultation' as NavScreen },
                { done: allDone, label: 'Наслаждайтесь', sub: '', screen: undefined },
              ].map((step, i) => {
                const isClickable = step.screen && onNavigate;
                const content = (
                  <>
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
                    <div className="min-w-0 text-left">
                      <p className={`text-sm font-medium ${step.done ? 'text-slate-700' : 'text-slate-900'}`}>{step.label}</p>
                      {step.sub && <p className="text-xs text-slate-500">{step.sub}</p>}
                    </div>
                  </>
                );
                return (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg border border-slate-100">
                    {isClickable ? (
                      <button
                        type="button"
                        onClick={() => onNavigate(step.screen!)}
                        className="flex items-center gap-3 w-full text-left rounded-lg -m-2 p-2 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-inset"
                      >
                        {content}
                      </button>
                    ) : (
                      content
                    )}
                  </div>
                );
              })}
            </div>
            {allDone && (
              <button
                type="button"
                onClick={() => {
                  if (typeof localStorage !== 'undefined') localStorage.setItem(PROGRESS_CLOSED_KEY, 'true');
                  setProgressClosed(true);
                }}
                className="mt-3 w-full py-2.5 px-4 rounded-button bg-slate-800 text-white font-medium text-sm hover:bg-slate-700 transition-colors"
              >
                Закрыть
              </button>
            )}
          </Card>
        );
      })()}

      {/* Цель месяца (фокус от ИИ) */}
      {!focusGoalLoading && focusGoal && (
        <Card className="p-4 mb-4 bg-white border border-slate-200 shadow-card">
          <h2 className="text-sm font-bold text-slate-900 mb-2">Цель этого месяца</h2>
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
          <h2 className="text-sm font-bold text-amber-900 mb-2">Обратите внимание</h2>
          <ul className="space-y-1 text-sm text-amber-800">
            {alertsData.alerts.map((a, i) => (
              <li key={i} className="flex items-center gap-2">
                <span>{a.text}</span>
                {(a.type === 'reserve_low' || a.type === 'reserve_ok') && (
                  <span
                    className="shrink-0 min-w-[44px] min-h-[44px] inline-flex items-center justify-center cursor-help"
                    title={RESERVE_ALERT_TOOLTIP}
                    aria-label="Подсказка"
                  >
                    <span className="w-6 h-6 rounded-full inline-flex items-center justify-center bg-amber-200/80 text-amber-900 text-xs font-medium">?</span>
                  </span>
                )}
              </li>
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

      {/* Блок 1: Денежный поток + Сравнение с целевыми нормами (визуально один блок) */}
      <div ref={cashFlowCardRef}>
        <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Денежный поток</h2>
            {stats && (
              <ShareButton
                captureRef={cashFlowCardRef}
                title="Денежный поток — FinAdvisor"
                text={`Денежный поток за ${MONTH_NAMES[selectedMonth - 1]} ${selectedYear}: расходы ${formatMoney(stats.total_expense)} ₽, доходы ${formatMoney(stats.total_income)} ₽, разница ${(stats.total_income - stats.total_expense) >= 0 ? '+' : '−'}${formatMoney(Math.abs(stats.total_income - stats.total_expense))} ₽`}
              />
            )}
        </div>
        {/* Селектор месяца: центрированный месяц и год со стрелками влево/вправо */}
        {(() => {
          const currentIndex = monthOptions.findIndex((o) => o.month === selectedMonth && o.year === selectedYear);
          const idx = currentIndex >= 0 ? currentIndex : 0;
          const canPrev = idx < monthOptions.length - 1;
          const canNext = idx > 0;
          return (
            <div className="flex items-center justify-center gap-3 py-1.5 px-3 mb-4 bg-slate-100 dark:bg-slate-700/60 rounded-lg">
              <button
                type="button"
                onClick={() => {
                  if (canPrev) {
                    const o = monthOptions[idx + 1];
                    setSelectedYear(o.year);
                    setSelectedMonth(o.month);
                  }
                }}
                disabled={!canPrev}
                className="flex items-center justify-center min-w-[44px] min-h-[32px] rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                aria-label="Предыдущий месяц"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div className="text-center min-w-[120px]">
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (canNext) {
                    const o = monthOptions[idx - 1];
                    setSelectedYear(o.year);
                    setSelectedMonth(o.month);
                  }
                }}
                disabled={!canNext}
                className="flex items-center justify-center min-w-[44px] min-h-[32px] rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:pointer-events-none transition-colors"
                aria-label="Следующий месяц"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          );
        })()}

        {statsLoading && (
          <div className="flex justify-center py-6">
            <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full animate-spin" />
          </div>
        )}
        {!statsLoading && statsError && (
          <div className="py-4 flex flex-col gap-3">
            <p className="text-sm text-slate-700 dark:text-slate-300">Не удалось загрузить данные. Проверьте интернет и попробуйте снова.</p>
            <button
              type="button"
              onClick={() => refetchStats()}
              className="self-start px-4 py-2 rounded-button bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900 text-sm font-medium hover:bg-slate-700 dark:hover:bg-slate-300"
            >
              Повторить
            </button>
          </div>
        )}
        {!statsLoading && stats && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-lg px-3 py-2 border border-income bg-white dark:bg-slate-800/50 dark:border-income/50">
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-0.5">Доходы</p>
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 break-all">{formatMoney(stats.total_income)} ₽</p>
              </div>
              <div className="rounded-lg px-3 py-2 border border-expense bg-white dark:bg-slate-800/50 dark:border-expense/50">
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-0.5">Расходы</p>
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 break-all">{formatMoney(stats.total_expense)} ₽</p>
              </div>
              <div
                className={`rounded-lg px-3 py-2 border ${
                  (stats.total_income - stats.total_expense) >= 0 ? 'bg-income/10 border-income/20 dark:bg-income/20 dark:border-income/50' : 'bg-expense/10 border-expense/20 dark:bg-expense/20 dark:border-expense/50'
                }`}
              >
                <p className="text-xs text-slate-600 dark:text-slate-400 mb-0.5">Разница</p>
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

            <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 mb-2">Разница по месяцам (последний год)</h3>
            {monthlyLoading ? (
              <div className="h-32 flex items-center justify-center text-slate-400 text-sm">Загрузка...</div>
            ) : (() => {
              const filtered = monthlyBalance.filter((d) => d.income !== 0 || d.expense !== 0);
              return filtered.length === 0 ? (
                <div className="py-4">
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">Нет данных за последний год.</p>
                  {onNavigate && (
                    <button
                      type="button"
                      onClick={() => onNavigate('finance')}
                      className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      Добавьте первую транзакцию →
                    </button>
                  )}
                </div>
              ) : (
                <DifferenceBarChart data={filtered} />
              );
            })()}
          </>
        )}

        {/* Сравнение с целевыми нормами: в том же блоке, таблица У вас / Цель */}
        {!benchmarksLoading && benchmarks && benchmarks.total_income > 0 && benchmarks.savings != null && (
          <>
            <hr className="my-4 border-slate-200" />
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300">Сравнение с целевыми нормами</h3>
              <button
                type="button"
                onClick={() => setBenchmarksHelpOpen(!benchmarksHelpOpen)}
                className="min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0 rounded-full"
                title="Как читать отчёт"
              >
                <span className="w-6 h-6 rounded-full flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200">?</span>
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
              <table className="w-full text-[10px] text-slate-500 dark:text-slate-400 border-collapse">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 pr-2 font-medium">Категория</th>
                    <th className="text-right py-2 px-2 font-medium">У вас</th>
                    <th className="text-right py-2 pl-2 font-medium">Цель</th>
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
                        <td className="text-right py-2 pl-2">
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
      </div>

      {/* Блок 2: Чистый капитал */}
      <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Чистый капитал</h2>
            <button
              type="button"
              onClick={() => setCapitalHelpOpen(!capitalHelpOpen)}
              className="min-w-[44px] min-h-[44px] flex items-center justify-center shrink-0 rounded-full"
              title="Пояснения"
            >
              <span className="w-6 h-6 rounded-full flex items-center justify-center bg-slate-100 text-slate-600 hover:bg-slate-200">?</span>
            </button>
          </div>
          {capitalSummary && (
            <ShareButton
              title="Чистый капитал — FinAdvisor"
              text={`Чистый капитал: активы ${formatMoney(capitalSummary.assets)} ₽, пассивы ${formatMoney(capitalSummary.liabilities)} ₽, итого ${formatMoney(capitalSummary.net)} ₽`}
            />
          )}
        </div>
        {capitalHelpOpen && (
          <div className="mb-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-200 dark:border-slate-600 text-xs text-slate-700 dark:text-slate-300">
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
              <div className="rounded-lg px-3 py-2 border border-income bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Активы</p>
                <p className="text-xs font-semibold text-slate-900 break-all">{formatMoney(capitalSummary.assets)} ₽</p>
              </div>
              <div className="rounded-lg px-3 py-2 border border-expense bg-white">
                <p className="text-xs text-slate-600 mb-0.5">Пассивы</p>
                <p className="text-xs font-semibold text-slate-900 break-all">{formatMoney(capitalSummary.liabilities)} ₽</p>
              </div>
              <div
                className={`rounded-lg px-3 py-2 border ${
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

            <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 mb-2">Финансовый путь</h3>
            {capitalHistoryLoading ? (
              <div className="h-48 flex items-center justify-center text-slate-400 text-sm">Загрузка...</div>
            ) : (() => {
              const filtered = capitalHistory.filter((d) => d.assets !== 0 || d.liabilities !== 0);
              return filtered.length === 0 ? (
                <div className="py-4">
                  <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">Нет данных по капиталу.</p>
                  {onNavigate && (
                    <button
                      type="button"
                      onClick={() => onNavigate('finance')}
                      className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      Добавьте активы и долги →
                    </button>
                  )}
                </div>
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
        <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-3">Последние рекомендации</h2>
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
                  const isPositive = d.net >= 0;
                  const labelOffset = isPositive ? 10 : (nvOverlapsAssets ? -22 : -18);
                  return (
                    <>
                      <span
                        className="absolute left-1/2 text-[9px] font-medium text-blue-600 whitespace-nowrap z-20"
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
