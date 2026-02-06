import { type ReactNode, useState, useEffect } from 'react';
import { BottomNav, type NavScreen } from './BottomNav';
import { fetchEnvInfo, type EnvInfo } from '@/lib/api';

interface AppLayoutProps {
  children: ReactNode;
  activeScreen: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

/** Обёртка экрана: контент + нижняя навигация. Масштабирование: на desktop добавить Sidebar и обёртку с grid. */
export function AppLayout({ children, activeScreen, onNavigate }: AppLayoutProps) {
  const [envInfo, setEnvInfo] = useState<EnvInfo | null | undefined>(undefined);

  useEffect(() => {
    fetchEnvInfo().then(setEnvInfo);
  }, []);

  const isTest = envInfo?.environment === 'test';

  return (
    <div className="min-h-screen flex flex-col">
      {isTest && (
        <div className="sticky top-0 z-50 bg-amber-500 text-amber-950 px-3 py-2 text-center text-sm font-medium shadow">
          Тестовая среда | БД: {envInfo?.db_name ?? '—'} @ {envInfo?.db_host ?? '—'}
        </div>
      )}
      <main className="flex-1 w-full max-w-[480px] mx-auto px-4 sm:px-6 pt-5 pb-24">
        {children}
      </main>
      <BottomNav active={activeScreen} onNavigate={onNavigate} />
    </div>
  );
}
