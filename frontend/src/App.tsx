import { useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardScreen } from '@/components/dashboard/DashboardScreen';
import type { NavScreen } from '@/components/layout/BottomNav';

/**
 * Корневой компонент. Роутинг по экранам через state.
 * Масштабирование: заменить на React Router при появлении глубоких ссылок и экранов Транзакции/Бюджеты/Капитал/Консультация/О приложении.
 */
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
