import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import type { NavScreen } from '@/components/layout/BottomNav';

/** Экран «Пользовательское соглашение». Текст можно заменить на полную версию. */
export function TermsScreen() {
  return (
    <div className="min-h-full text-slate-900 dark:text-slate-100 pb-6">
      <PageHeader title="Пользовательское соглашение" />

      <Card className="p-4 mb-4 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-card">
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4 italic">
          Страница на стадии разработки, скоро будет красиво.
        </p>
        <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
          <p className="mb-3 leading-relaxed">
            Настоящее Пользовательское соглашение регулирует порядок использования мини-приложения FinAdvisor в Telegram.
          </p>
          <p className="mb-3 leading-relaxed">
            Используя приложение, вы подтверждаете, что ознакомились с условиями и принимаете их. Разместите здесь полный текст пользовательского соглашения.
          </p>
        </div>
        <div className="mt-4">
          <Button
            type="button"
            variant="primary"
            className="w-full py-3.5"
            onClick={() => {
              window.dispatchEvent(new CustomEvent<NavScreen>('app:navigate', { detail: 'profile' }));
            }}
          >
            Ознакомился
          </Button>
        </div>
      </Card>
    </div>
  );
}
