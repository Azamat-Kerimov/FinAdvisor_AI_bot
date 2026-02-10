import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/api';
import type {
  Stats,
  MonthlyBalanceItem,
  CapitalSummary,
  CapitalHistoryItem,
  ConsultationHistoryItem,
  BenchmarksResponse,
  ProgressVsSelfResponse,
  OnboardingProgressResponse,
  AlertsResponse,
  FocusGoalResponse,
  ConsultationActionItem,
  BadgesResponse,
  SimulatorResponse,
} from '@/types/api';

/** Предыдущий месяц (число 1–12 и год) */
export function getPreviousMonth(): { month: number; year: number } {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return { month: d.getMonth() + 1, year: d.getFullYear() };
}

/** Загрузка статистики за выбранный месяц. По умолчанию — предыдущий месяц. */
export function useStats(month?: number, year?: number) {
  const prev = getPreviousMonth();
  const m = month ?? prev.month;
  const y = year ?? prev.year;
  const [data, setData] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const url = `/api/stats?month=${m}&year=${y}`;
    apiRequest<Stats>(url, { signal: controller.signal })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled && e?.name !== 'AbortError') {
          setError(e instanceof Error ? e : new Error(String(e)));
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [m, y, refetchTrigger]);

  const refetch = () => setRefetchTrigger((t) => t + 1);
  return { data, loading, error, refetch };
}

/** Доходы, расходы и разница по месяцам за последние 12 месяцев */
export function useMonthlyBalance() {
  const [data, setData] = useState<MonthlyBalanceItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiRequest<MonthlyBalanceItem[]>('/api/stats/monthly')
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading };
}

/** Текущие активы, долги и чистый капитал */
export function useCapitalSummary() {
  const [data, setData] = useState<CapitalSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiRequest<CapitalSummary>('/api/capital/summary')
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading };
}

/** История активов/долгов на конец каждого из последних 12 месяцев */
export function useCapitalHistory() {
  const [data, setData] = useState<CapitalHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiRequest<CapitalHistoryItem[]>('/api/capital/history')
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading };
}

/** Последние консультации (для саммари на главной) */
export function useConsultationHistory() {
  const [data, setData] = useState<ConsultationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiRequest<ConsultationHistoryItem[]>('/api/consultation/history')
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading };
}

/** Бенчмарки: доли по категориям и целевые диапазоны */
export function useBenchmarks() {
  const [data, setData] = useState<BenchmarksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    apiRequest<BenchmarksResponse>('/api/benchmarks')
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  return { data, loading };
}

/** Прогресс относительно себя (3 мес. назад vs последние 3 мес.) */
export function useProgressVsSelf() {
  const [data, setData] = useState<ProgressVsSelfResponse | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    apiRequest<ProgressVsSelfResponse>('/api/progress-vs-self')
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  return { data, loading };
}

/** Прогресс онбординга (пайплайн) */
export function useOnboardingProgress() {
  const [data, setData] = useState<OnboardingProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    apiRequest<OnboardingProgressResponse>('/api/onboarding-progress')
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  return { data, loading };
}

/** Мягкие алерты */
export function useAlerts() {
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    apiRequest<AlertsResponse>('/api/alerts')
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  return { data, loading };
}

/** Цель на этот месяц (фокус от ИИ) */
export function useFocusGoal() {
  const [data, setData] = useState<FocusGoalResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refetch, setRefetch] = useState(0);
  useEffect(() => {
    let cancelled = false;
    apiRequest<FocusGoalResponse | null>('/api/focus-goal')
      .then((res) => { if (!cancelled) setData(res ?? null); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refetch]);
  return { data, loading, refetch: () => setRefetch((n) => n + 1) };
}

/** Чек-лист действий из консультации */
export function useConsultationActions() {
  const [data, setData] = useState<ConsultationActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refetch, setRefetch] = useState(0);
  useEffect(() => {
    let cancelled = false;
    apiRequest<ConsultationActionItem[]>('/api/consultation/actions')
      .then((res) => { if (!cancelled) setData(Array.isArray(res) ? res : []); })
      .catch(() => { if (!cancelled) setData([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refetch]);
  return { data, loading, refetch: () => setRefetch((n) => n + 1) };
}

/** Бейджи прогресса */
export function useBadges() {
  const [data, setData] = useState<BadgesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    apiRequest<BadgesResponse>('/api/badges')
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  return { data, loading };
}

/** Симулятор (goal_months, debt_months). Вызывать с (goalId, monthlySavings) или monthlyPayment. */
export function useSimulator(goalId?: number | null, monthlySavings?: number | null, monthlyPayment?: number | null) {
  const [data, setData] = useState<SimulatorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const hasGoal = goalId != null && monthlySavings != null && monthlySavings > 0;
    const hasDebt = monthlyPayment != null && monthlyPayment > 0;
    if (!hasGoal && !hasDebt) {
      setData(null);
      return;
    }
    const params = new URLSearchParams();
    if (goalId != null) params.set('goal_id', String(goalId));
    if (monthlySavings != null && monthlySavings > 0) params.set('monthly_savings', String(monthlySavings));
    if (monthlyPayment != null && monthlyPayment > 0) params.set('monthly_payment', String(monthlyPayment));
    let cancelled = false;
    setLoading(true);
    apiRequest<SimulatorResponse>(`/api/simulator?${params}`)
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [goalId ?? 0, monthlySavings ?? 0, monthlyPayment ?? 0]);
  return { data, loading };
}
