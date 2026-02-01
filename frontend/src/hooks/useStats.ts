import { useState, useEffect } from 'react';
import { apiRequest } from '@/lib/api';
import type { Stats } from '@/types/api';

/** Загрузка статистики с главного экрана. При ошибке/таймауте возвращает null. */
export function useStats() {
  const [data, setData] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiRequest<Stats>('/api/stats', { signal: controller.signal })
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
  }, []);

  return { data, loading, error };
}
