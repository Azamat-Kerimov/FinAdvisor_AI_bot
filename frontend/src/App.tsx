import { useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardScreen } from '@/components/dashboard/DashboardScreen';
import { TransactionsScreen } from '@/components/transactions/TransactionsScreen';
import { CapitalScreen } from '@/components/capital/CapitalScreen';
import { ConsultationScreen } from '@/components/consultation/ConsultationScreen';
import type { NavScreen } from '@/components/layout/BottomNav';

function App() {
  const [screen, setScreen] = useState<NavScreen>('dashboard');

  return (
    <AppLayout activeScreen={screen} onNavigate={setScreen}>
      {screen === 'dashboard' && <DashboardScreen />}
      {screen === 'transactions' && <TransactionsScreen />}
      {screen === 'capital' && <CapitalScreen />}
      {screen === 'consultation' && <ConsultationScreen />}
    </AppLayout>
  );
}

export default App;
