#!/bin/bash
# Создаёт App.tsx в src/, если его нет (для серверов, где файл не подтянулся из git).
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
FILE="$DIR/src/App.tsx"
if [ -f "$FILE" ]; then
  echo "App.tsx already exists."
  exit 0
fi
mkdir -p "$(dirname "$FILE")"
cat > "$FILE" << 'ENDOFAPP'
import { useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardScreen } from '@/components/dashboard/DashboardScreen';
import type { NavScreen } from '@/components/layout/BottomNav';

function App() {
  const [screen, setScreen] = useState<NavScreen>('dashboard');

  return (
    <AppLayout activeScreen={screen} onNavigate={setScreen}>
      {screen === 'dashboard' && <DashboardScreen />}
      {screen === 'transactions' && (
        <div className="py-8 text-center text-muted">
          Экран «Транзакции» — подключите роутер и компонент списка операций.
        </div>
      )}
      {screen === 'capital' && (
        <div className="py-8 text-center text-muted">
          Экран «Капитал» — активы и долги.
        </div>
      )}
      {screen === 'consultation' && (
        <div className="py-8 text-center text-muted">
          Экран «Консультация» — чат с ИИ.
        </div>
      )}
    </AppLayout>
  );
}

export default App;
ENDOFAPP
echo "Created $FILE"
