const API_BASE = import.meta.env.VITE_API_URL ?? '';

export interface EnvInfo {
  environment: string;
  db_name: string;
  db_host: string;
}

let envInfo: EnvInfo | null | undefined = undefined;

/** В тесте (APP_ENV=test) возвращает данные о среде и БД; иначе null. Вызов не блокирует запросы. */
export async function fetchEnvInfo(): Promise<EnvInfo | null> {
  if (envInfo !== undefined) return envInfo;
  try {
    const r = await fetch(`${API_BASE}/api/env-info`);
    if (r.status === 404 || !r.ok) {
      envInfo = null;
      return null;
    }
    envInfo = (await r.json()) as EnvInfo;
    return envInfo;
  } catch {
    envInfo = null;
    return null;
  }
}

function getInitData(): string {
  if (typeof window !== 'undefined' && (window as unknown as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData) {
    return (window as unknown as { Telegram: { WebApp: { initData: string } } }).Telegram.WebApp.initData;
  }
  return '';
}

/** Заголовки для запросов к API (в т.ч. multipart/file). В тесте добавляет X-Test-User-Id. */
export async function getApiHeaders(extra: HeadersInit = {}): Promise<HeadersInit> {
  const initData = getInitData();
  const headers: HeadersInit = { ...extra };
  if (initData) {
    (headers as Record<string, string>)['init-data'] = initData;
  } else {
    const env = await fetchEnvInfo();
    if (env?.environment === 'test') {
      (headers as Record<string, string>)['X-Test-User-Id'] =
        typeof localStorage !== 'undefined' ? localStorage.getItem('finadvisor_test_user_id') || '1' : '1';
    }
  }
  return headers;
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(initData ? { 'init-data': initData } : {}),
    ...options.headers,
  };
  if (!initData) {
    const env = await fetchEnvInfo();
    if (env?.environment === 'test') {
      (headers as Record<string, string>)['X-Test-User-Id'] =
        typeof localStorage !== 'undefined' ? localStorage.getItem('finadvisor_test_user_id') || '1' : '1';
    }
  }
  const controller = new AbortController();
  // Для /api/consultation нужен больший таймаут (до 60 секунд на бэкенде)
  const timeoutMs = endpoint === '/api/consultation' ? 65_000 : 10_000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      signal: options.signal ?? controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) {
      const text = await res.text();
      if (res.status === 401) throw new Error('Требуется авторизация. Откройте приложение через Telegram.');
      if (res.status === 403 && (text.includes('PREMIUM') || text.includes('premium'))) {
        throw new Error('Требуется подписка. Оформите подписку в боте.');
      }
      throw new Error(text || `Ошибка: ${res.status}`);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    clearTimeout(timeoutId);
    // Улучшаем сообщение об ошибке при прерывании запроса
    if (e instanceof Error && e.name === 'AbortError') {
      throw new Error('Запрос был прерван по таймауту. Попробуйте ещё раз.');
    }
    throw e;
  }
}

/**
 * Логирование действия пользователя в БД (экран, шаринг и т.д.).
 * Вызов не блокирует UI; ошибки игнорируются.
 */
export function logAction(action: string, details?: Record<string, unknown>): void {
  apiRequest<{ status: string }>('/api/log-action', {
    method: 'POST',
    body: JSON.stringify({ action, details }),
  }).catch(() => {
    // fire-and-forget
  });
}
