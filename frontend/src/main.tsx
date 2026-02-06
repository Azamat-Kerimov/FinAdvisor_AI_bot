import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';

// Telegram Mini App: открыть в FullScreen (на весь экран), а не в Compact/FullSize
function initTelegramFullScreen() {
  const tg = (window as unknown as {
    Telegram?: {
      WebApp?: {
        ready?: () => void;
        expand?: () => void;
        requestFullscreen?: () => void;
      };
    };
  }).Telegram?.WebApp;
  if (!tg) return;
  tg.ready?.();
  tg.expand?.();
  // Bot API 8.0+: настоящий полноэкран (без шапки Telegram)
  if (typeof tg.requestFullscreen === 'function') {
    tg.requestFullscreen();
  }
}
if (typeof window !== 'undefined') {
  requestAnimationFrame(() => initTelegramFullScreen());
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
