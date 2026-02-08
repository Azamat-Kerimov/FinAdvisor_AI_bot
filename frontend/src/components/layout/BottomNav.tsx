export type NavScreen = 'dashboard' | 'transactions' | 'capital' | 'consultation' | 'profile' | 'help';

interface BottomNavProps {
  active: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

const items: { id: NavScreen; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Главная', icon: '🏠' },
  { id: 'transactions', label: 'Транзакции', icon: '💰' },
  { id: 'capital', label: 'Капитал', icon: '💼' },
  { id: 'consultation', label: 'ИИ', icon: '🤖' },
  { id: 'profile', label: 'Профиль', icon: '👤' },
  { id: 'help', label: 'Помощь', icon: '❓' },
];

/** Нижняя навигация (mobile). Масштабирование: на desktop рендерить Sidebar с теми же items. */
export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around bg-white border-t border-border min-h-[72px] py-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-2px_12px_rgba(0,0,0,0.04)]">
      {items.map(({ id, label, icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onNavigate(id)}
          className={`flex flex-col items-center justify-center gap-1 rounded-button transition-colors min-w-[72px] min-h-[56px] py-2 px-3 ${
            active === id ? 'text-slate-900' : 'text-muted hover:text-slate-600'
          }`}
        >
          <span className="text-[24px] leading-none" aria-hidden>{icon}</span>
          <span className="text-[11px] font-medium leading-tight text-center">{label}</span>
        </button>
      ))}
    </nav>
  );
}
