import { useState, useRef, useEffect } from 'react';

export type NavScreen = 'dashboard' | 'transactions' | 'capital' | 'consultation' | 'scenarios' | 'profile' | 'help';

interface BottomNavProps {
  active: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

const mainItems: { id: NavScreen; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Главная', icon: '🏠' },
  { id: 'transactions', label: 'Транзакции', icon: '💰' },
  { id: 'capital', label: 'Капитал', icon: '💼' },
  { id: 'consultation', label: 'ИИ', icon: '🤖' },
  { id: 'scenarios', label: 'Сценарии', icon: '📊' },
];

const moreItems: { id: NavScreen; label: string; icon: string }[] = [
  { id: 'profile', label: 'Профиль', icon: '👤' },
  { id: 'help', label: 'Помощь', icon: '❓' },
];

/** Нижняя навигация (mobile). Пункты «Профиль» и «Помощь» в выпадающем «Ещё». */
export function BottomNav({ active, onNavigate }: BottomNavProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (menuOpen && menuRef.current && !menuRef.current.contains(target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  function handleMoreItem(id: NavScreen) {
    onNavigate(id);
    setMenuOpen(false);
  }

  const isMoreActive = moreItems.some((item) => item.id === active);

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around bg-white dark:bg-slate-900 border-t border-border dark:border-slate-700 min-h-[72px] py-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-2px_12px_rgba(0,0,0,0.04)]">
      {mainItems.map(({ id, label, icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onNavigate(id)}
          className={`flex flex-col items-center justify-center gap-0.5 sm:gap-1 rounded-button transition-colors min-w-0 flex-1 max-w-[72px] min-h-[56px] py-2 px-1 sm:px-3 ${
            active === id ? 'text-slate-900 dark:text-white' : 'text-muted hover:text-slate-600 dark:hover:text-slate-300'
          }`}
        >
          <span className="text-[24px] leading-none" aria-hidden>{icon}</span>
          <span className="text-xs font-medium leading-tight text-center truncate w-full min-w-0">{label}</span>
        </button>
      ))}
      <div className="relative min-w-0 flex-1 max-w-[72px] flex justify-center" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          className={`flex flex-col items-center justify-center gap-0.5 sm:gap-1 rounded-button transition-colors min-h-[56px] py-2 px-1 sm:px-3 ${
            isMoreActive ? 'text-slate-900 dark:text-white' : 'text-muted hover:text-slate-600 dark:hover:text-slate-300'
          }`}
          aria-expanded={menuOpen}
          aria-haspopup="true"
        >
          <span className="text-[24px] leading-none" aria-hidden>⋯</span>
          <span className="text-xs font-medium leading-tight text-center">Ещё</span>
        </button>
        {menuOpen && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-40 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg py-1 z-10">
            {moreItems.map(({ id, label, icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => handleMoreItem(id)}
                className={`w-full flex items-center gap-2 px-4 py-3 text-left text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                  active === id
                    ? 'bg-slate-100 dark:bg-slate-700 text-slate-900 dark:text-white font-medium'
                    : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700'
                }`}
              >
                <span className="text-lg leading-none" aria-hidden>{icon}</span>
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
