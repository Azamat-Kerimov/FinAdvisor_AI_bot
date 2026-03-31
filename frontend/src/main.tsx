import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { setTelegramHeaderForTheme } from '@/lib/telegramTheme';
import './index.css';

/** Фиксированная светлая палитра: не подстраиваемся под тёмную тему Telegram. */
function applyFixedLightTelegramColors() {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.style.setProperty('--tg-bg', '#f4f4f5');
  root.style.setProperty('--tg-secondary-bg', '#ffffff');
  root.style.setProperty('--tg-section-bg', 'rgba(255,255,255,0.9)');
  root.style.setProperty('--tg-text', '#000000');
  root.style.setProperty('--tg-hint', '#999999');
  root.style.setProperty('--tg-link', '#2481cc');
  root.style.setProperty('--tg-panel', '#ffffff');
  root.style.setProperty('--tg-border', '#e5e5e5');
}

// Telegram Mini App: FullScreen, всегда светлые цвета и шапка
function initTelegramFullScreen() {
  const tg = (window as unknown as {
    Telegram?: {
      WebApp?: {
        ready?: () => void;
        expand?: () => void;
        requestFullscreen?: () => void;
        onEvent?: (e: string, fn: () => void) => void;
      };
    };
  }).Telegram?.WebApp;
  if (!tg) return;
  tg.ready?.();
  tg.expand?.();
  applyFixedLightTelegramColors();
  if (typeof tg.onEvent === 'function') {
    tg.onEvent('themeChanged', applyFixedLightTelegramColors);
  }
  setTelegramHeaderForTheme('light');
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
