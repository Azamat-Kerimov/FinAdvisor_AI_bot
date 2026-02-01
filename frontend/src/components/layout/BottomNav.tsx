export type NavScreen = 'dashboard' | 'transactions' | 'capital' | 'consultation';

interface BottomNavProps {
  active: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

const items: { id: NavScreen; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Главная', icon: '🏠' },
  { id: 'transactions', label: 'Транзакции', icon: '💰' },
  { id: 'capital', label: 'Капитал', icon: '💼' },
  { id: 'consultation', label: 'ИИ', icon: '🤖' },
];

/** Нижняя навигация (mobile). Масштабирование: на desktop рендерить Sidebar с теми же items. */
export function BottomNav({ active, onNavigate }: BottomNavProps) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around bg-white border-t border-border py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-2px_12px_rgba(0,0,0,0.04)]">
      {items.map(({ id, label, icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onNavigate(id)}
          className={`flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-button text-[11px] font-medium transition-colors min-w-[64px] ${
            active === id ? 'text-slate-900' : 'text-muted hover:text-slate-600'
          }`}
        >
          <span className="text-[22px] leading-none">{icon}</span>
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
