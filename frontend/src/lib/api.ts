const API_BASE = import.meta.env.VITE_API_URL ?? '';

function getInitData(): string {
  if (typeof window !== 'undefined' && (window as unknown as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData) {
    return (window as unknown as { Telegram: { WebApp: { initData: string } } }).Telegram.WebApp.initData;
  }
  return '';
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(initData ? { 'init-data': initData } : {}),
    ...options.headers,
  };
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10_000);
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
    throw e;
  }
}
