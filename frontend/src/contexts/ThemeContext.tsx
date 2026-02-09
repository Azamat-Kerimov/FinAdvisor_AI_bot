import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { setTelegramHeaderForTheme } from '@/lib/telegramTheme';

const STORAGE_KEY = 'finadvisor_theme';

export type Theme = 'light' | 'dark' | 'system';

/** Установить класс темы до первого рендера (уменьшает мерцание). */
function applyInitialTheme() {
  if (typeof document === 'undefined') return;
  const stored = localStorage.getItem(STORAGE_KEY);
  const theme: Theme = stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
  let resolved: 'light' | 'dark' = theme === 'light' ? 'light' : theme === 'dark' ? 'dark' : (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.classList.remove('light', 'dark');
  document.documentElement.classList.add(resolved);
}
applyInitialTheme();

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolved: 'light' | 'dark';
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getStored(): Theme {
  if (typeof localStorage === 'undefined') return 'system';
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === 'light' || v === 'dark' || v === 'system') return v;
  return 'system';
}

function getResolved(theme: Theme): 'light' | 'dark' {
  if (theme === 'light') return 'light';
  if (theme === 'dark') return 'dark';
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
  return 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStored);
  const [resolved, setResolved] = useState<'light' | 'dark'>(() => getResolved(theme));

  useEffect(() => {
    const resolvedTheme = getResolved(theme);
    setResolved(resolvedTheme);
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(resolvedTheme);
  }, [theme]);

  useEffect(() => {
    if (theme !== 'system') return;
    const m = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => {
      const next = getResolved('system');
      setResolved(next);
      setTelegramHeaderForTheme(next);
    };
    m.addEventListener('change', handler);
    return () => m.removeEventListener('change', handler);
  }, [theme]);

  useEffect(() => {
    setTelegramHeaderForTheme(resolved);
  }, [resolved]);

  const setTheme = (value: Theme) => {
    setThemeState(value);
    localStorage.setItem(STORAGE_KEY, value);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolved }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
