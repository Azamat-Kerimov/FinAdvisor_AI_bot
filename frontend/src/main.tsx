import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { setTelegramHeaderForTheme } from '@/lib/telegramTheme';
import './index.css';

type ThemeParams = Record<string, string> | undefined;

function applyTelegramThemeParams(themeParams: ThemeParams) {
  if (!themeParams || typeof document === 'undefined') return;
  const root = document.documentElement;
  if (themeParams.bg_color) root.style.setProperty('--tg-bg', themeParams.bg_color);
  if (themeParams.secondary_bg_color) root.style.setProperty('--tg-secondary-bg', themeParams.secondary_bg_color);
  if (themeParams.text_color) root.style.setProperty('--tg-text', themeParams.text_color);
  if (themeParams.hint_color) root.style.setProperty('--tg-hint', themeParams.hint_color);
  if (themeParams.link_color) root.style.setProperty('--tg-link', themeParams.link_color);
}

// Telegram Mini App: FullScreen, цвета из themeParams, шапка под статус-бар
function initTelegramFullScreen() {
  const tg = (window as unknown as {
    Telegram?: {
      WebApp?: {
        ready?: () => void;
        expand?: () => void;
        requestFullscreen?: () => void;
        colorScheme?: 'light' | 'dark';
        themeParams?: ThemeParams;
        onEvent?: (e: string, fn: () => void) => void;
      };
    };
  }).Telegram?.WebApp;
  if (!tg) return;
  tg.ready?.();
  tg.expand?.();
  applyTelegramThemeParams(tg.themeParams);
  if (typeof tg.onEvent === 'function') {
    tg.onEvent('themeChanged', () => applyTelegramThemeParams(tg.themeParams));
  }
  const scheme = tg.colorScheme === 'dark' ? 'dark' : 'light';
  setTelegramHeaderForTheme(scheme);
  if (typeof tg.requestFullscreen === 'function') {
    tg.requestFullscreen();
  }
}
if (typeof window !== 'undefined') {
  requestAnimationFrame(() => initTelegramFullScreen());
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
