import { useState, useRef, useEffect } from 'react';

export type NavScreen = 'dashboard' | 'finance' | 'consultation' | 'scenarios' | 'profile' | 'help' | 'feedback' | 'terms' | 'privacy';

interface BottomNavProps {
  active: NavScreen;
  onNavigate: (screen: NavScreen) => void;
}

/** Упрощённые иконки таббара (stroke). Размер задаётся через width/height для масштабирования. */
const iconSize = 24;
const iconSizeMore = 24;
const strokeWidth = 2;

function IconHome({ className, size = iconSize }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function IconWallet({ className, size = iconSize }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
      <path d="M17 14a1 1 0 1 0 0 2 1 1 0 0 0 0-2z" />
    </svg>
  );
}

function IconBot({ className, size = iconSize }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="8.5" cy="16" r="1" />
      <circle cx="15.5" cy="16" r="1" />
      <path d="M8.5 11V8a3.5 3.5 0 0 1 7 0v3" />
    </svg>
  );
}

function IconChart({ className, size = iconSize }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

function IconMore({ className, size = iconSize }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <circle cx="12" cy="12" r="1" />
      <circle cx="6" cy="12" r="1" />
      <circle cx="18" cy="12" r="1" />
    </svg>
  );
}

function IconProfile({ className, size = iconSizeMore }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconHelp({ className, size = iconSizeMore }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function IconFeedback({ className, size = iconSizeMore }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}


const mainItems: { id: NavScreen; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'dashboard', label: 'Главная', Icon: IconHome },
  { id: 'finance', label: 'Финансы', Icon: IconWallet },
  { id: 'scenarios', label: 'Сценарии', Icon: IconChart },
  { id: 'consultation', label: 'ИИ', Icon: IconBot },
];

const moreItems: { id: NavScreen; label: string; Icon: React.ComponentType<{ className?: string; size?: number }> }[] = [
  { id: 'profile', label: 'Профиль', Icon: IconProfile },
  { id: 'help', label: 'Помощь', Icon: IconHelp },
  { id: 'feedback', label: 'Обратная связь', Icon: IconFeedback },
];

/** Нижняя навигация в стиле Telegram: 5 вкладок в общем таббаре, кнопка «Ещё» отдельно. */
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
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex items-end justify-center gap-1.5 px-2 sm:px-3 pt-1.5 pb-[max(0.5rem,calc(env(safe-area-inset-bottom)+10px))] bg-transparent pointer-events-none"
      aria-label="Навигация"
    >
      <div className="pointer-events-auto flex items-stretch gap-1.5 flex-1 max-w-[480px] min-w-0">
        {/* Основной таббар: 5 вкладок в сильно закруглённом «пилюлеобразном» блоке */}
        <div className="flex-1 flex items-center justify-around rounded-full bg-white/90 dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700 min-h-[50px] px-1 shadow-[0_4px_12px_rgba(15,23,42,0.18)]">
          {mainItems.map(({ id, label, Icon }) => {
            const isActive = active === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onNavigate(id)}
                className={`flex flex-col items-center justify-center gap-0 flex-1 min-w-0 max-w-[64px] min-h-[42px] rounded-md transition-colors ${
                  isActive
                    ? 'bg-slate-200/80 dark:bg-slate-600 text-savings dark:text-sky-400'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
              >
                <Icon />
                <span className={`text-[11px] sm:text-[12px] font-medium leading-tight truncate w-full text-center mt-0.5 ${isActive ? 'text-savings dark:text-sky-400' : ''}`}>
                  {label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Кнопка «Ещё» отдельно справа (уменьшена) */}
        <div className="relative shrink-0" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className={`flex flex-col items-center justify-center w-11 h-11 sm:w-12 sm:h-12 rounded-full border shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors ${
              isMoreActive
                ? 'bg-slate-200/80 dark:bg-slate-600 border-slate-300 dark:border-slate-600 text-savings dark:text-sky-400'
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
            aria-expanded={menuOpen}
            aria-haspopup="true"
            aria-label="Ещё"
          >
            <IconMore />
            <span className={`text-[11px] font-medium leading-tight mt-0.5 ${isMoreActive ? 'text-savings dark:text-sky-400' : ''}`}>
              Ещё
            </span>
          </button>
          {menuOpen && (
            <div className="absolute bottom-full right-0 mb-1.5 w-52 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-[0_2px_8px_rgba(0,0,0,0.08)] py-0.5 z-10">
              {moreItems.map(({ id, label, Icon: MoreIcon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleMoreItem(id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left text-sm transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    active === id
                      ? 'bg-slate-100 dark:bg-slate-700 text-savings dark:text-sky-400 font-medium'
                      : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700'
                  }`}
                >
                  <MoreIcon size={iconSizeMore} />
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
