# FinAdvisor — фронтенд (React + TypeScript + Tailwind)

## Запуск

```bash
cd frontend
npm install
npm run dev
```

Приложение откроется на `http://localhost:5173`. API проксируется на `http://127.0.0.1:8000` (см. `vite.config.ts`).

## Сборка

```bash
npm run build
```

Результат в `frontend/dist`. Раздавать через тот же backend (FastAPI) или nginx.

## Дизайн и масштабирование

- **Паттерны и структура страниц:** см. [DESIGN.md](./DESIGN.md).
- **Масштабирование:** комментарии в компонентах (`Card`, `Button`, `PageHeader`, `BottomNav`, `StatsCards`, `InsightBlock`, `DashboardScreen`, `App.tsx`).

## Переменные окружения

- `VITE_API_URL` — базовый URL API (по умолчанию пусто, запросы идут на тот же origin или через proxy).

## Если на сервере npm install падает (Killed) или нет tailwindcss

1. Установить с ограничением памяти: `NODE_OPTIONS=--max-old-space-size=512 npm install`
2. Либо поставить только нужное для сборки: `npm install -D tailwindcss postcss autoprefixer`
3. Убедиться, что на сервере есть все файлы из `src/` (в т.ч. `src/components/layout/`, `src/components/dashboard/`) — при необходимости сделать `git pull` или скопировать папку `frontend` с машины, где всё есть.
