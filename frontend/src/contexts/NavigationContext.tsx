import { createContext, useContext, type ReactNode } from 'react';
import type { NavScreen } from '@/components/layout/BottomNav';

interface NavigationContextValue {
  onNavigate: (screen: NavScreen) => void;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

export function NavigationProvider({ onNavigate, children }: { onNavigate: (screen: NavScreen) => void; children: ReactNode }) {
  return (
    <NavigationContext.Provider value={{ onNavigate }}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigation(): NavigationContextValue | null {
  return useContext(NavigationContext);
}
