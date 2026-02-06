import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/api';
import type {
  Stats,
  MonthlyBalanceItem,
  CapitalSummary,
  CapitalHistoryItem,
  ConsultationHistoryItem,
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
  }, [m, y]);

  return { data, loading, error };
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

/** Текущие активы, пассивы и чистый капитал */
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

/** История активов/пассивов на конец каждого из последних 12 месяцев */
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
