import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { setTelegramHeaderForTheme } from '@/lib/telegramTheme';

const STORAGE_KEY = 'finadvisor_theme';
const LIGHT_ONLY: Theme = 'light';

export type Theme = 'light' | 'dark' | 'system';

/** Светлая тема до первого рендера (без мерцания тёмной темы). */
function applyInitialTheme() {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.remove('light', 'dark');
  document.documentElement.classList.add('light');
  try {
    localStorage.setItem(STORAGE_KEY, 'light');
  } catch {
    /* ignore */
  }
}
applyInitialTheme();

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolved: 'light' | 'dark';
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.documentElement.classList.remove('dark');
    document.documentElement.classList.add('light');
    setTelegramHeaderForTheme('light');
  }, []);

  const setTheme = (_value: Theme) => {
    document.documentElement.classList.remove('dark');
    document.documentElement.classList.add('light');
    try {
      localStorage.setItem(STORAGE_KEY, 'light');
    } catch {
      /* ignore */
    }
    setTelegramHeaderForTheme('light');
  };

  return (
    <ThemeContext.Provider value={{ theme: LIGHT_ONLY, setTheme, resolved: 'light' }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
