import { useState, useEffect } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardScreen } from '@/components/dashboard/DashboardScreen';
import { TransactionsScreen } from '@/components/transactions/TransactionsScreen';
import { CapitalScreen } from '@/components/capital/CapitalScreen';
import { ConsultationScreen } from '@/components/consultation/ConsultationScreen';
import { ScenarioScreen } from '@/components/scenarios/ScenarioScreen';
import { ProfileScreen } from '@/components/profile/ProfileScreen';
import { HelpScreen } from '@/components/help/HelpScreen';
import type { NavScreen } from '@/components/layout/BottomNav';
import { logAction } from '@/lib/api';

function App() {
  const [screen, setScreen] = useState<NavScreen>('dashboard');

  useEffect(() => {
    logAction('screen_view', { screen });
  }, [screen]);

  return (
    <AppLayout activeScreen={screen} onNavigate={setScreen}>
      {screen === 'dashboard' && <DashboardScreen onNavigate={setScreen} />}
      {screen === 'transactions' && <TransactionsScreen />}
      {screen === 'capital' && <CapitalScreen />}
      {screen === 'consultation' && <ConsultationScreen />}
      {screen === 'scenarios' && <ScenarioScreen />}
      {screen === 'profile' && <ProfileScreen />}
      {screen === 'help' && <HelpScreen />}
    </AppLayout>
  );
}

export default App;
