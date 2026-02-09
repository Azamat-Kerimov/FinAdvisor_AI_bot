import { useState, useEffect } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardScreen } from '@/components/dashboard/DashboardScreen';
import { FinanceScreen } from '@/components/finance/FinanceScreen';
import { ConsultationScreen } from '@/components/consultation/ConsultationScreen';
import { ScenarioScreen } from '@/components/scenarios/ScenarioScreen';
import { ProfileScreen } from '@/components/profile/ProfileScreen';
import { HelpScreen } from '@/components/help/HelpScreen';
import { FeedbackScreen } from '@/components/feedback/FeedbackScreen';
import { TermsScreen } from '@/components/legal/TermsScreen';
import { PrivacyScreen } from '@/components/legal/PrivacyScreen';
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
      {screen === 'finance' && <FinanceScreen />}
      {screen === 'consultation' && <ConsultationScreen />}
      {screen === 'scenarios' && <ScenarioScreen />}
      {screen === 'profile' && <ProfileScreen />}
      {screen === 'help' && <HelpScreen />}
      {screen === 'feedback' && <FeedbackScreen />}
      {screen === 'terms' && <TermsScreen />}
      {screen === 'privacy' && <PrivacyScreen />}
    </AppLayout>
  );
}

export default App;
