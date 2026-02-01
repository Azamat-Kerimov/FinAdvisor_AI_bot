import { type ReactNode } from 'react';
import { BottomNav, type NavScreen } from './BottomNav';

interface AppLayoutProps {
  children: ReactNode;
  activeScreen: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

/** Обёртка экрана: контент + нижняя навигация. Масштабирование: на desktop добавить Sidebar и обёртку с grid. */
export function AppLayout({ children, activeScreen, onNavigate }: AppLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 w-full max-w-[480px] mx-auto px-4 sm:px-6 pb-24">
        {children}
      </main>
      <BottomNav active={activeScreen} onNavigate={onNavigate} />
    </div>
  );
}
